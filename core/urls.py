from django.urls import path
from . import views

urlpatterns = [
    path('autenticacao/', views.autenticacao, name='autenticacao'),
    path('detalhes/', views.detalhes, name='detalhes'),
    path('listagem/', views.listagem, name='listagem'),
    path('perguntar/', views.perguntar, name='perguntar'),
]
