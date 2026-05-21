from datetime import timedelta

from django.http import HttpRequest
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import FormAdminUsuario, FormCadastro, FormLogin, FormPerfil, FormPergunta, FormResposta, FormStaffToken
from .models import Perfil, Pergunta, Resposta, StaffToken

# Funções Auxiliares
def administrador(usuario):
    return usuario.is_superuser

def moderador(usuario):
    return usuario.is_staff or administrador(usuario)

def dentro_do_prazo(objeto, dias=1):
    return timezone.now() <= objeto.criado_em + timedelta(days=dias)

def enviar_confirmacao_email(pedido, usuario):
    pass

def pode_editar(objeto, usuario):
    return objeto.autor_id == usuario.id and dentro_do_prazo(objeto)

def pode_excluir(objeto, usuario):
    return moderador(usuario) or pode_editar(objeto, usuario)

def pode_fechar(objeto, usuario):
    if moderador(usuario): return True
    if objeto.reaberta_por_id: return objeto.reaberta_por_id == usuario.id
    else: return objeto.autor_id == usuario.id

# Views
@login_required(login_url='autenticacao')
@user_passes_test(administrador, login_url='listagem')
def administracao(request: HttpRequest):
    """Página de administração de usuários."""

    # Listagem de tokens e usuários
    tokens = StaffToken.objects.select_related('criado_por', 'usado_por')
    usuarios = User.objects.select_related('perfil').order_by('first_name', 'username')

    # Cria formulários
    form_token = FormStaffToken(request.POST or None)
    forms_usuarios = []
    for usuario in usuarios:
        if (request.method == 'POST' and request.POST.get('acao') == 'editar_usuario' and
            request.POST.get('usuario_id') == str(usuario.pk)):
            form = FormAdminUsuario(request.POST)
        else:
            form = FormAdminUsuario(initial={
                'first_name': usuario.first_name,
                'departamento': getattr(usuario.perfil, 'departamento', None),
            })
        forms_usuarios.append({ 'usuario': usuario, 'form': form })

    # Responde aos endpoints
    novo_codigo = None
    if request.method == 'POST':
        match request.POST.get('acao'):
            case 'alternar_ativo_usuario':
                usuario = get_object_or_404(User, pk=request.POST.get('usuario'))
                if usuario.is_superuser:
                    messages.error(request, 'Não é possível desativar um administrador.')
                else:
                    usuario.is_active = not usuario.is_active
                    usuario.save(update_fields=['is_active'])
                    if usuario.is_active:
                        messages.success(request, 'Usuário reativado com sucesso.')
                    else:
                        messages.success(request, 'Usuário desativado com sucesso.')
                return redirect('administracao')
            case 'criar_token':
                 if form_token.is_valid():
                    _, novo_codigo = StaffToken.criar(criado_por=request.user, descricao=form_token.cleaned_data['descricao'])
                    messages.success(request, 'Token de moderador criado com sucesso.')
            case 'desmoderar_usuario':
                usuario = get_object_or_404(User, pk=request.POST.get('usuario'))
                if usuario.is_superuser:
                    messages.error(request, 'Não é possível desmoderar um administrador.')
                elif not usuario.is_staff:
                    messages.error(request, 'Este usuário não é moderador.')
                else:
                    usuario.is_staff = False
                    usuario.save(update_fields=['is_staff'])
                    messages.success(request, 'Usuário não é mais um moderador.')
                return redirect('administracao')
            case 'editar_usuario':
                usuario = get_object_or_404(User, pk=request.POST.get('usuario'))
                form = FormAdminUsuario(request.POST)
                if form.is_valid():
                    usuario.first_name = form.cleaned_data['first_name']
                    usuario.save(update_fields=['first_name'])
                    Perfil.objects.update_or_create(usuario=usuario, defaults={ 'departamento': form.cleaned_data['departamento'] })
                    messages.success(request, 'Usuário atualizado com sucesso.')
                    return redirect('administracao')
            case 'revogar_token':
                token = get_object_or_404(StaffToken, pk=request.POST.get('token_id'))
                if token.usado_em:
                    messages.error(request, 'Este token já foi utilizado.')
                elif not token.ativo:
                    messages.error(request, 'Este token já está revogado.')
                else:
                    token.ativo = False
                    token.save(update_fields=['ativo'])
                    messages.success(request, 'Token revogado com sucesso.')
                return redirect('administracao')

    # Renderiza página
    return render(request, 'administracao.html', {
        'form_token': form_token,
        'forms_usuarios': forms_usuarios,
        'novo_codigo': novo_codigo,
        'tokens': tokens,
    })

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
        modificavel = moderador(request.user) or pergunta.status != 'fechada'
        resposta.pode_editar = modificavel and pode_editar(resposta, request.user)
        resposta.pode_excluir = modificavel and pode_excluir(resposta, request.user)

    # Cria formulário de resposta
    editando_id = None
    form_editar_resposta = None
    form_resposta = FormResposta()
    if request.method == 'POST':
        match request.POST.get('acao'):
            case 'editar_resposta':
                resposta = get_object_or_404(Resposta, pk=request.POST.get('resposta_id'), pergunta=pergunta)
                if not moderador(request.user) and pergunta.status == 'fechada':
                    messages.error(request, 'A resposta não pode ser editada quando a pergunta está fechada.')
                elif pode_editar(resposta, request.user):
                    form_editar_resposta = FormResposta(instance=resposta)
                    editando_id = resposta.pk
                else:
                    messages.error(request, 'O prazo para editar esta resposta expirou.')
            case 'excluir_pergunta':
                if not moderador(request.user) and pergunta.status == 'fechada':
                    messages.error(request, 'A pergunta não pode ser excluida quando fechada.')
                elif pode_excluir(pergunta, request.user):
                    pergunta.delete()
                    messages.success(request, 'Pergunta excluída com sucesso.')
                    return redirect('listagem')
                else:
                    messages.error(request, 'Você não pode excluir esta pergunta.')
                    return redirect('detalhes', id=pergunta.pk)
            case 'excluir_resposta':
                resposta = get_object_or_404(Resposta, pk=request.POST.get('resposta_id'), pergunta=pergunta)
                if not moderador(request.user) and pergunta.status == 'fechada':
                    messages.error(request, 'A resposta não pode ser excluida quando a pergunta está fechada.')
                elif pode_excluir(resposta, request.user):
                    resposta.delete()
                    if not pergunta.respostas.exists() and pergunta.status in ['respondida', 'fechada']:
                        pergunta.status = 'aberta'
                        pergunta.save(update_fields=['status'])
                    messages.success(request, 'Resposta excluída com sucesso.')
                else:
                    messages.error(request, 'O prazo para excluir esta resposta expirou.')
                return redirect('detalhes', id=pergunta.pk)
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
            case 'reabrir_pergunta':
                motivo = request.POST.get('motivo_reabertura', '').strip()
                if pergunta.status != 'fechada':
                    messages.error(request, 'Esta pergunta não está fechada.')
                elif len(motivo) < 10:
                    messages.error(request, 'Informe um motivo com ao menos 10 caracteres.')
                else:
                    pergunta.status = 'aberta'
                    pergunta.motivo_reabertura = motivo
                    pergunta.reaberta_em = timezone.now()
                    pergunta.reaberta_por = request.user
                    pergunta.save(update_fields=['status', 'motivo_reabertura', 'reaberta_em', 'reaberta_por'])
                    messages.success(request, 'Pergunta reaberta com sucesso.')
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
        'pode_editar_pergunta': pode_editar(pergunta, request.user) and not pergunta.motivo_reabertura and pergunta.status != 'fechada',
        'pode_excluir_pergunta': pode_excluir(pergunta, request.user) and (moderador(request.user) or pergunta.status != 'fechada'),
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
    perguntas = perguntas.annotate(movimentada_em=Coalesce('reaberta_em', 'criado_em')).order_by('-movimentada_em')

    # Renderiza página com as perguntas filtradas
    return render(request, 'listagem.html', {
        'busca': search,
        'perguntas': perguntas,
        'status_filtro': status,
        'status_opcoes': Pergunta.STATUS_CHOICES,
    })

@login_required(login_url='autenticacao')
def perfil(request: HttpRequest):
    form = FormPerfil(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        email_antigo = request.user.email
        user = form.save()
        messages.success(request, 'Perfil atualizado com sucesso.')
        if user.email != email_antigo:
            enviar_confirmacao_email(request, user)
            #logout(request)
            #messages.info(request, 'Confirme o novo e-mail para acessar sua conta novamente.')
            #return redirect('autenticacao')
        return redirect('perfil')
    return render(request, 'perfil.html', { 'form': form })

@login_required(login_url='autenticacao')
def perguntar(request: HttpRequest, id: int | None = None):
    """Criação de nova pergunta."""

    # Obtém possível pergunta já existente
    pergunta = None
    if id:
        pergunta = get_object_or_404(Pergunta, pk=id)
        if pergunta.status == 'fechada':
            messages.error(request, 'A pergunta não pode ser editada quando fechada.')
            return redirect('detalhes', id=pergunta.pk)
        elif pergunta.motivo_reabertura:
            messages.error(request, 'A pergunta não pode ser editada se já foi reaberta.')
            return redirect('detalhes', id=pergunta.pk)
        elif not pode_editar(pergunta, request.user):
            messages.error(request, 'O prazo para editar esta pergunta expirou.')
            return redirect('detalhes', id=pergunta.pk)

    # Salva a pergunta no banco de dados
    form_pergunta = FormPergunta(data=request.POST or None, instance=pergunta)
    pergunta_existente_id = None
    if request.method == 'POST':
        if form_pergunta.is_valid():
            pergunta = form_pergunta.save(commit=False)
            if not pergunta.pk:
                pergunta.autor = request.user
            pergunta.save()
            messages.success(request, 'Pergunta atualizada com sucesso.' if id else 'Pergunta criada com sucesso.')
            return redirect('detalhes', id=pergunta.pk)
        else:
            erros = form_pergunta.non_field_errors()
            for erro in erros:
                if str(erro).startswith('PERGUNTA_EXISTENTE:'):
                    pergunta_existente_id = str(erro).split(':')[1]
                    break

    # Renderiza página
    return render(request, 'perguntar.html', {
        'form_pergunta': form_pergunta,
        'pergunta_existente_id': pergunta_existente_id,
        'subtitulo': 'Atualize sua dúvida.' if id else 'Descreva sua dúvida com detalhes.',
        'texto_botao': 'Salvar' if id else 'Perguntar',
        'titulo_pagina': 'Editar Pergunta' if id else 'Nova Pergunta',
    })

@login_required(login_url='autenticacao')
def sair(request: HttpRequest):
    logout(request)
    return redirect('autenticacao')
