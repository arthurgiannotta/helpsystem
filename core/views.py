from django.http import HttpRequest
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FormCadastro, FormLogin, FormPergunta, FormResposta
from .models import Pergunta

def autenticacao(request: HttpRequest):
    """Página de login e cadastro."""

    # Redireciona usuário já logado
    if request.user.is_authenticated:
        return redirect('listagem')

    # Responde aos endpoints
    form_login = FormLogin()
    form_cadastro = FormCadastro()
    if request.method == 'POST':
        match request.POST.get('acao'):
            case 'cadastro':
                form_cadastro = FormCadastro(data=request.POST)
                if form_cadastro.is_valid():
                    user = form_cadastro.save()
                    login(request, user)
                    messages.success(request, 'Cadastro realizado com sucesso!')
                    return redirect('listagem')
            case 'login':
                form_login = FormLogin(data=request.POST)
                if form_login.is_valid():
                    user = form_login.get_user()
                    login(request, user)
                    return redirect('listagem')
                else:
                    messages.error(request, 'Usuário ou senha inválidos.')

    # Renderiza página
    return render(request, 'autenticacao.html', {
        'form_cadastro': form_cadastro,
        'form_login': form_login,
    })

@login_required(login_url='autenticacao')
def detalhes(request: HttpRequest, id: int):
    """Detalhes sobre a pergunta (data/autor/...). Listagem e adição de respostas."""

    # Obtém dados da pergunta
    pergunta = get_object_or_404(Pergunta.objects.select_related('autor', 'autor__perfil'), pk=id)
    respostas = pergunta.respostas.select_related('autor', 'autor__perfil')

    # Cria formulário de resposta
    form_resposta = FormResposta()
    if request.method == 'POST':
        form_resposta = FormResposta(request.POST)
        if form_resposta.is_valid():
            resposta = form_resposta.save(commit=False)
            resposta.autor = request.user
            resposta.pergunta = pergunta
            resposta.save()
            if pergunta.status == 'aberta':
                pergunta.status = 'respondida'
                pergunta.save()
            messages.success(request, 'Resposta enviada!')
            return redirect('detalhes', id=id)

    # Renderiza página
    return render(request, 'detalhes.html', {
        'pergunta': pergunta,
        'respostas': respostas,
        'form_resposta': form_resposta,
    })

@login_required(login_url='autenticacao')
def listagem(request: HttpRequest):
    """Filtragem e listagem de perguntas."""

    # Busca perguntas (junto ao autor para otimização da página)
    perguntas = Pergunta.objects.select_related('autor', 'autor__perfil').all()

    # Filtra perguntas
    search = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    if search:
        perguntas = perguntas.filter(Q(titulo__icontains=search) | Q(autor__first_name__icontains=search))
    if status:
        perguntas = perguntas.filter(status=status)

    # Renderiza página com as perguntas filtradas
    return render(request, 'listagem.html', {
        'busca': search,
        'perguntas': perguntas,
        'status_filtro': status,
        'status_opcoes': Pergunta.STATUS_CHOICES,
    })

@login_required(login_url='autenticacao')
def perguntar(request: HttpRequest):
    """Criação de nova pergunta."""

    # Salva a pergunta no banco de dados
    form_pergunta = FormPergunta()
    if request.method == 'POST':
        form_pergunta = FormPergunta(data=request.POST)
        if form_pergunta.is_valid():
            pergunta = form_pergunta.save(commit=False)
            pergunta.autor = request.user
            pergunta.save()
            messages.success(request, 'Pergunta criada com sucesso!')
            return redirect('detalhes', id=pergunta.pk)

    # Renderiza página
    return render(request, 'perguntar.html', { 'form_pergunta': form_pergunta })

@login_required(login_url='autenticacao')
def sair(request: HttpRequest):
    logout(request)
    return redirect('autenticacao')
