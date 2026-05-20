from datetime import timedelta

from django.http import HttpRequest
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import FormCadastro, FormLogin, FormPergunta, FormReabrirPergunta, FormResposta
from .models import Pergunta, Resposta

# Funções Auxiliares
def administrador(usuario):
    return usuario.is_staff or usuario.is_superuser

def dentro_do_prazo(objeto, dias=1):
    return timezone.now() <= objeto.criado_em + timedelta(days=dias)

def pode_editar(objeto, usuario):
    return objeto.autor_id == usuario.id and dentro_do_prazo(objeto)

def pode_excluir(objeto, usuario):
    return administrador(usuario) or pode_editar(objeto, usuario)

def pode_fechar(objeto, usuario):
    return administrador(usuario) or objeto.autor_id == usuario.id

# Views
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
    for resposta in respostas:
        resposta.pode_editar = pode_editar(resposta, request.user)
        resposta.pode_excluir = pode_excluir(resposta, request.user)

    # Cria formulário de resposta
    editando_id = None
    form_editar_resposta = None
    form_resposta = FormResposta()
    if request.method == 'POST':
        match request.POST.get('acao'):
            case 'editar_resposta':
                resposta = get_object_or_404(Resposta, pk=request.POST.get('resposta_id'), pergunta=pergunta)
                if pode_editar(resposta, request.user):
                    form_editar_resposta = FormResposta(instance=resposta)
                    editando_id = resposta.pk
                else:
                    messages.error(request, 'O prazo para editar esta resposta expirou.')
            case 'fechar_pergunta':
                if pergunta.status == 'fechada':
                    messages.info(request, 'Esta pergunta já está fechada.')
                elif not pergunta.respostas.exists():
                    messages.error(request, 'A pergunta precisa ter ao menos uma resposta para ser fechada.')
                elif not pode_fechar(pergunta, request.user):
                    messages.error(request, 'Você não pode fechar esta pergunta.')
                else:
                    pergunta.status = 'fechada'
                    pergunta.save(update_fields=['status'])
                    messages.success(request, 'Pergunta fechada com sucesso.')
                return redirect('detalhes', id=pergunta.pk)
            case 'excluir_resposta':
                resposta = get_object_or_404(Resposta, pk=request.POST.get('resposta_id'), pergunta=pergunta)
                if pode_excluir(resposta, request.user):
                    resposta.delete()
                    if not pergunta.respostas.exists() and pergunta.status in ['respondida', 'fechada']:
                        pergunta.status = 'aberta'
                        pergunta.save(update_fields=['status'])
                    messages.success(request, 'Resposta excluída com sucesso.')
                else:
                    messages.error(request, 'O prazo para excluir esta resposta expirou.')
                return redirect('detalhes', id=pergunta.pk)
            case 'responder':
                if pergunta.status == 'fechada':
                    messages.error(request, 'Reabra a pergunta antes de responder.')
                    return redirect('detalhes', id=id)
                form_resposta = FormResposta(request.POST)
                if form_resposta.is_valid():
                    resposta = form_resposta.save(commit=False)
                    resposta.autor = request.user
                    resposta.pergunta = pergunta
                    resposta.save()
                    if pergunta.status == 'aberta':
                        pergunta.status = 'respondida'
                        pergunta.save(update_fields=['status'])
                    messages.success(request, 'Resposta enviada!')
                    return redirect('detalhes', id=id)
            case 'salvar_resposta':
                resposta = get_object_or_404(Resposta, pk=request.POST.get('resposta_id'), pergunta=pergunta)
                if pode_editar(resposta, request.user):
                    form_editar_resposta = FormResposta(request.POST, instance=resposta)
                    if resposta.resposta != request.POST.get('resposta', '') and form_editar_resposta.is_valid():
                        form_editar_resposta.save()
                        messages.success(request, 'Resposta atualizada com sucesso.')
                        return redirect('detalhes', id=pergunta.pk)
                else:
                    messages.error(request, 'O prazo para editar esta resposta expirou.')

    # Renderiza página
    return render(request, 'detalhes.html', {
        'editando_id': editando_id,
        'pergunta': pergunta,
        'respostas': respostas,
        'form_editar_resposta': form_editar_resposta,
        'form_resposta': form_resposta,
        'pode_fechar_pergunta': pode_fechar(pergunta, request.user) and pergunta.status != 'fechada' and len(respostas) > 0,
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
    pergunta_existente_id = None
    if request.method == 'POST':
        form_pergunta = FormPergunta(data=request.POST)
        if form_pergunta.is_valid():
            pergunta = form_pergunta.save(commit=False)
            pergunta.autor = request.user
            pergunta.save()
            messages.success(request, 'Pergunta criada com sucesso!')
            return redirect('detalhes', id=pergunta.pk)
        else:
            erros = form_pergunta.non_field_errors()
            for erro in erros:
                if str(erro).startswith('PERGUNTA_EXISTENTE:'):
                    pergunta_existente_id = str(erro).split(':')[1]
                    break

    # Renderiza página
    return render(request, 'perguntar.html', { 'form_pergunta': form_pergunta, 'pergunta_existente_id': pergunta_existente_id, })

@login_required(login_url='autenticacao')
def sair(request: HttpRequest):
    logout(request)
    return redirect('autenticacao')
