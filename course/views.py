from django.http import Http404
from django.shortcuts import render, get_object_or_404
# Create your views here.
from django.urls import reverse_lazy
from django.views.generic import CreateView

from course.forms import ProblemCreateForm
from course.models import Question, MultipleChoiceQuestion, Submission


class ProblemCreateView(CreateView):
    model = Question
    form_class = ProblemCreateForm
    template_name = 'problem_create.html'
    success_url = reverse_lazy('course:new_problem')


def multiple_choice_question_view(request, question):
    if request.method == 'POST':
        answer = request.POST.get('answer', None)

        submission = Submission()
        submission.user = request.user
        submission.answer = answer
        submission.question = question

        submission.save()

    return render(request, 'multiple_choice_question.html', {
        'question': question,
        'submissions': question.submissions.filter(user=request.user).all(),
    })


def question_view(request, pk):
    question = get_object_or_404(Question, pk=pk)

    if isinstance(question, MultipleChoiceQuestion):
        return multiple_choice_question_view(request, question)

    raise Http404()


def problem_set_view(request):
    problems = Question.objects.all()

    return render(request, 'problem_set.html', {
        'problems': problems,
    })