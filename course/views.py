from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.forms import formset_factory
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy

from accounts.utils.decorators import show_login
from course.forms import ProblemFilterForm, MultipleChoiceQuestionForm, CheckboxQuestionForm, \
    JavaQuestionForm, ChoiceForm
from course.models import Question, MultipleChoiceQuestion, CheckboxQuestion, JavaQuestion, JavaSubmission, \
    QuestionCategory, DIFFICULTY_CHOICES, TokenValue, MultipleChoiceSubmission
from course.utils import get_token_value, get_user_question_junction, increment_char, create_multiple_choice_question, \
    QuestionCreateException


@show_login('You need to be logged in to create a question')
def _multiple_choice_question_create_view(request, header, question_form_class, correct_answer_formset_class,
                                          distractor_answer_formset_class):
    if request.method == 'POST':
        correct_answer_formset = correct_answer_formset_class(request.POST, prefix='correct')
        distractor_answer_formset = distractor_answer_formset_class(request.POST, prefix='distractor')
        form = question_form_class(request.POST)

        if correct_answer_formset.is_valid() and distractor_answer_formset.is_valid() and form.is_valid():

            try:
                question = create_multiple_choice_question(
                    title=form.cleaned_data['title'],
                    text=form.cleaned_data['text'],
                    author=request.user,
                    category=form.cleaned_data['category'],
                    difficulty=form.cleaned_data['difficulty'],
                    visible_distractor_count=form.cleaned_data['visible_distractor_count'],
                    answer_text=correct_answer_formset.forms[0].cleaned_data['text'],
                    distractors=[form.cleaned_data['text'] for form in distractor_answer_formset.forms if not form.cleaned_data['DELETE']],
                )
                messages.add_message(request, messages.SUCCESS, 'Problem was created successfully')
                form = question_form_class()
                correct_answer_formset = correct_answer_formset_class(prefix='correct')
                distractor_answer_formset = distractor_answer_formset_class(prefix='distractor')
                
            except QuestionCreateException as e:
                messages.add_message(request, messages.ERROR, e.user_message)
    else:
        form = question_form_class()

        correct_answer_formset = correct_answer_formset_class(prefix='correct')
        distractor_answer_formset = distractor_answer_formset_class(prefix='distractor')

    return render(request, 'problem_create.html', {
        'form': form,
        'correct_answer_formset': correct_answer_formset,
        'distractor_answer_formset': distractor_answer_formset,
        'header': header,
    })


@show_login('You need to be logged in to create a question')
def _java_question_create_view(request, header, question_form_class):
    if request.method == 'POST':
        form = question_form_class(request.POST)

        if form.is_valid():
            question = form.save()
            question.author = request.user
            question.is_verified = request.user.is_teacher()
            question.save()

            messages.add_message(request, messages.SUCCESS, 'Problem was created successfully')

            form = question_form_class()
    else:
        form = question_form_class()

    return render(request, 'problem_create.html', {
        'form': form,
        'header': header,
    })


def java_question_create_view(request):
    return _java_question_create_view(request, 'New Java Question', JavaQuestionForm)


def multiple_choice_question_create_view(request):
    return _multiple_choice_question_create_view(
        request,
        'New Multiple Choice Question',
        MultipleChoiceQuestionForm,
        formset_factory(ChoiceForm, extra=1, can_delete=True, max_num=1, min_num=1),
        formset_factory(ChoiceForm, extra=2, can_delete=True),
    )


def checkbox_question_create_view(request):
    return _multiple_choice_question_create_view(
        request,
        'New Checkbox Question',
        CheckboxQuestionForm,
        formset_factory(ChoiceForm, extra=1, can_delete=True),
        formset_factory(ChoiceForm, extra=2, can_delete=True),
    )


def multiple_choice_question_view(request, question, template_name):
    if request.method == 'POST':

        answer = request.POST.get('answer', None)
        if not answer:
            answer = request.POST.getlist('answer[]')
        answer = str(answer)

        if not request.user.is_authenticated:
            messages.add_message(request, messages.ERROR, 'You need to be logged in to submit answers')
        elif not question.is_allowed_to_submit(request.user):
            messages.add_message(request, messages.ERROR, 'Maximum number of submissions reached')
        elif request.user.submissions.filter(question=question, answer=answer).exists():
            messages.add_message(request, messages.INFO, 'You have already submitted this answer!')
        else:
            submission = MultipleChoiceSubmission()
            submission.user = request.user
            submission.answer = answer
            submission.question = question

            submission.save()

            if submission.is_correct:
                received_tokens = get_user_question_junction(request.user, question).tokens_received
                messages.add_message(
                    request, messages.SUCCESS,
                    'Answer submitted. Your answer was correct. You received {} tokens'.format(received_tokens),
                )
            else:
                messages.add_message(
                    request, messages.ERROR,
                    'Answer submitted. Your answer was wrong',
                )

    return render(request, template_name, {
        'question': question,
        'statement': question.get_rendered_text(request.user),
        'choices': question.get_rendered_choices(request.user),
        'submissions': question.submissions.filter(
            user=request.user).all() if request.user.is_authenticated else MultipleChoiceSubmission.objects.none(),
        'submission_allowed': question.is_allowed_to_submit(request.user),
    })


def java_question_view(request, question):
    def return_render():
        return render(request, 'java_question.html', {
            'question': question,
            'submissions': question.submissions.filter(
                user=request.user).all() if request.user.is_authenticated else JavaSubmission.objects.none(),
            'submission_allowed': question.is_allowed_to_submit(request.user),
        })

    if request.method == "POST":

        answer_text = request.POST.get('answer-text', "")
        answer_file = request.FILES.get('answer-file', None)

        answer_text = answer_text.strip()

        if answer_text == "" and not answer_file:
            messages.add_message(request, messages.ERROR, "Please either submit the code as text or upload a java file")
            return return_render()

        if answer_text != "" and answer_file:
            messages.add_message(request, messages.ERROR,
                                 "Both text and file was submitted please. Please only submit a text or a file")
            return return_render()

        if answer_file:
            answer_text = answer_file.read().decode("ascii", "ignore")

        if not request.user.is_authenticated:
            messages.add_message(request, messages.ERROR, 'You need to be logged in to submit answers')
        elif not question.is_allowed_to_submit(request.user):
            messages.add_message(request, messages.ERROR, 'Maximum number of submissions reached')
        elif request.user.submissions.filter(question=question, code=answer_text).exists():
            messages.add_message(request, messages.INFO, 'You have already submitted this answer!')
        else:
            submission = JavaSubmission()
            submission.user = request.user
            submission.code = answer_text
            submission.question = question

            submission.submit()

            messages.add_message(request, messages.INFO, "Your Code has been submitted and being evaluated!")

            return HttpResponseRedirect(reverse_lazy('course:question_view', kwargs={'pk': question.pk}))

    return return_render()


def question_view(request, pk):
    question = get_object_or_404(Question, pk=pk)

    if isinstance(question, JavaQuestion):
        return java_question_view(request, question)

    if isinstance(question, CheckboxQuestion):
        return multiple_choice_question_view(request, question, 'checkbox_question.html')

    if isinstance(question, MultipleChoiceQuestion):
        return multiple_choice_question_view(request, question, 'multiple_choice_question.html')

    raise Http404()


def teacher_check(user):
    return not user.is_anonymous and user.is_teacher()


@user_passes_test(teacher_check)
def multiple_choice_question_edit_view(request, question):
    correct_answer_formset_class = formset_factory(ChoiceForm, extra=1, can_delete=True, max_num=1, min_num=1)
    distractor_answer_formset_class = formset_factory(ChoiceForm, extra=0, can_delete=True)

    if request.method == 'POST':
        correct_answer_formset = correct_answer_formset_class(request.POST, prefix='correct')
        distractor_answer_formset = distractor_answer_formset_class(request.POST, prefix='distractor')
        form = MultipleChoiceQuestionForm(request.POST)

        if correct_answer_formset.is_valid() and distractor_answer_formset.is_valid() and form.is_valid():
            try:
                create_multiple_choice_question(
                    pk=question.pk,
                    title=form.cleaned_data['title'],
                    text=form.cleaned_data['text'],
                    max_submission_allowed=question.max_submission_allowed,
                    author=request.user,
                    category=form.cleaned_data['category'],
                    difficulty=form.cleaned_data['difficulty'],
                    is_verified=question.is_verified,
                    visible_distractor_count=form.cleaned_data['visible_distractor_count'],
                    answer_text=correct_answer_formset.forms[0].cleaned_data['text'],
                    distractors=[form.cleaned_data['text'] for form in distractor_answer_formset.forms],
                )
                messages.add_message(request, messages.SUCCESS, 'Problem saved successfully')
            except QuestionCreateException as e:
                messages.add_message(request, messages.ERROR, e.user_message)

    else:
        form = MultipleChoiceQuestionForm(instance=question)

        correct_answer_formset = correct_answer_formset_class(prefix='correct',
                                                              initial=[{'text': question.choices[question.answer]}])
        distractor_answer_formset = distractor_answer_formset_class(prefix='distractor', initial=
        [{'text': value} for name, value in question.choices.items() if name != question.answer]
                                                                    )

    return render(request, 'problem_create.html', {
        'form': form,
        'correct_answer_formset': correct_answer_formset,
        'distractor_answer_formset': distractor_answer_formset,
        'header': 'Edit Question',
    })


def question_edit_view(request, pk):
    question = get_object_or_404(Question, pk=pk)

    if isinstance(question, MultipleChoiceQuestion):
        return multiple_choice_question_edit_view(request, question)

    raise Http404()


def problem_set_view(request):
    query = request.GET.get('query', None)
    difficulty = request.GET.get('difficulty', None)
    solved = request.GET.get('solved', None)
    category = request.GET.get('category', None)

    q = Q(is_verified=True)

    if query:
        q = q & Q(title__contains=query)
    if difficulty:
        q = q & Q(difficulty=difficulty)
    if category:
        q = q & (Q(category=category) | Q(category__parent=category))

    problems = Question.objects.filter(q).all()

    for problem in problems:
        problem.token_value = get_token_value(problem.category, problem.difficulty)

        problem.is_solved = problem.is_solved_by_user(request.user)
        problem.is_partially_correct = problem.is_partially_correct_by_user(request.user)
        problem.no_submission = problem.has_no_submission_by_user(request.user)
        problem.is_wrong = not problem.is_solved and not problem.no_submission and not problem.is_partially_correct

    if solved == 'Solved':
        problems = [p for p in problems if p.is_solved]
    if solved == 'Unsolved':
        problems = [p for p in problems if not p.is_solved]
    if solved == "Partially Correct":
        problems = [p for p in problems if p.is_partially_correct]
    if solved == 'Wrong':
        problems = [p for p in problems if p.is_wrong]
    if solved == 'New':
        problems = [p for p in problems if p.no_submission]

    form = ProblemFilterForm(request.GET)

    return render(request, 'problem_set.html', {
        'problems': problems,
        'form': form,
        'header': 'problem_set',
    })


def java_submission_detail_view(request, pk):
    java_submission = get_object_or_404(JavaSubmission, pk=pk)

    if java_submission.user != request.user:
        raise Http404()

    return render(request, 'java_submission_detail.html', {
        'submission': java_submission,
    })


def token_values_table_view(request):
    if not request.user.is_teacher:
        raise PermissionDenied()

    query_set = QuestionCategory.objects.filter(parent__isnull=False).all()

    if request.method == 'POST':
        sent_values = request.POST.getlist('values[]', None)
        values = []

        for i, category in enumerate(query_set):
            values.append(sent_values[i * len(DIFFICULTY_CHOICES):(i + 1) * len(DIFFICULTY_CHOICES)])

            for j, difficulty in enumerate([x for x, y in DIFFICULTY_CHOICES]):
                token_value = TokenValue.objects.get(category=category, difficulty=difficulty)
                token_value.value = sent_values[i * len(DIFFICULTY_CHOICES) + j]
                token_value.save()
    else:
        values = []

        for category in query_set:
            values.append([])

            for difficulty, x in DIFFICULTY_CHOICES:

                if TokenValue.objects.filter(category=category, difficulty=difficulty).exists():
                    token_value = TokenValue.objects.get(category=category, difficulty=difficulty)
                else:
                    token_value = TokenValue(category=category, difficulty=difficulty)
                    token_value.save()

                values[-1].append(token_value.value)

    return render(request, 'token_values_table.html', {
        'values': values,
        'difficulties': [x for d, x in DIFFICULTY_CHOICES],
        'categories': query_set,
        'header': 'token_values',
    })
