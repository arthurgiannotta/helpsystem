from django.shortcuts import render

def autenticacao(request):
    return render(request, 'autenticacao.html')

def detalhes(request):
    return render(request, 'detalhes.html')

def listagem(request):
    return render(request, 'listagem.html')

def perguntar(request):
    return render(request, 'perguntar.html')
