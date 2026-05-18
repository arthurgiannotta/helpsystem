from django.http import HttpRequest
from django.shortcuts import render

def autenticacao(request: HttpRequest):
    """Página de login e cadastro."""
    return render(request, 'autenticacao.html')

def detalhes(request: HttpRequest):
    """Detalhes sobre a pergunta (data/autor/...). Listagem e adição de respostas."""
    return render(request, 'detalhes.html')

def listagem(request: HttpRequest):
    """Filtragem e listagem de perguntas."""
    return render(request, 'listagem.html')

def perguntar(request: HttpRequest):
    """Criação de nova pergunta."""
    return render(request, 'perguntar.html')
