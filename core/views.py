from django.http import HttpRequest
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import FormCadastro, FormLogin

def autenticacao(request: HttpRequest):
    """Página de login e cadastro."""
    
    # Redireciona usuário já logado
    if request.user.is_authenticated:
        return redirect('listagem')

    # Responde aos endpoints
    if request.method == 'POST':
        match request.POST.get('acao'):
            case 'cadastro':
                form_cadastro = FormCadastro(data=request.POST)
                if form_cadastro.is_valid():
                    user = form_cadastro.save()
                    login(request, user)
                    messages.success(request, 'Cadastro realizado com sucesso!')
                    return redirect('perguntas')
            case 'login':
                form_login = FormLogin(data=request.POST)
                if form_login.is_valid():
                    user = form_login.get_user()
                    login(request, user)
                    return redirect('perguntas')
                else:
                    messages.error(request, 'Usuário ou senha inválidos.')

    # Cria formulários
    form_login = FormLogin()
    form_cadastro = FormCadastro()
    return render(request, 'autenticacao.html', {
        'form_cadastro': form_cadastro,
        'form_login': form_login,
    })

@login_required(login_url='autenticacao')
def detalhes(request: HttpRequest):
    """Detalhes sobre a pergunta (data/autor/...). Listagem e adição de respostas."""
    return render(request, 'detalhes.html')

@login_required(login_url='autenticacao')
def listagem(request: HttpRequest):
    """Filtragem e listagem de perguntas."""
    return render(request, 'listagem.html')

@login_required(login_url='autenticacao')
def perguntar(request: HttpRequest):
    """Criação de nova pergunta."""
    return render(request, 'perguntar.html')
