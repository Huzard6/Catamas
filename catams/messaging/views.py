from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages as dj_messages
from .models import Message
from .forms import ComposeForm

@login_required
def inbox(request):
    msgs = Message.objects.filter(recipient=request.user).select_related('sender')
    return render(request, 'messaging/messages.html', {'tab': 'inbox', 'messages_list': msgs, 'form': ComposeForm()})

@login_required
def sent(request):
    msgs = Message.objects.filter(sender=request.user).select_related('recipient')
    return render(request, 'messaging/messages.html', {'tab': 'sent', 'messages_list': msgs, 'form': ComposeForm()})

@login_required
def compose(request):
    if request.method == 'POST':
        form = ComposeForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                sender=request.user,
                recipient=form.cleaned_data['to'],
                subject=form.cleaned_data['subject'],
                body=form.cleaned_data['body'],
            )
            dj_messages.success(request, 'Message sent.')
            return redirect('messaging:sent')
    else:
        form = ComposeForm()
    return render(request, 'messaging/messages.html', {'tab': 'compose', 'form': form})

@login_required
def read(request, pk):
    m = get_object_or_404(Message, pk=pk)
    if m.recipient != request.user and m.sender != request.user:
        return redirect('messaging:inbox')
    if m.recipient == request.user and not m.is_read:
        m.is_read = True
        m.save(update_fields=['is_read'])
    return render(request, 'messaging/messages.html', {'tab': 'read', 'm': m, 'form': ComposeForm()})