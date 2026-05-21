from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Perfil, Pergunta, Resposta, StaffToken


class Command(BaseCommand):
    departamentos = ['ti', 'rh', 'fin', 'jur', 'ma', 'ou']
    help = 'Cria dados de demonstração em português brasileiro.'
    senha_padrao = 'teste1234'
    perguntas_demo = [
        {
            'status': 'fechada',
            'autor': 'Valerio',
            'titulo': 'Como solicitar reembolso de despesas de viagem?',
            'pergunta': 'Preciso registrar despesas de uma viagem corporativa recente. Qual é o fluxo correto para solicitar o reembolso?',
            'respostas': [
                ('Arthur Clemente', 'Você deve anexar os comprovantes no portal financeiro e informar o centro de custo do projeto.'),
                ('Anabelle', 'Também é importante enviar a solicitação em até cinco dias úteis após o retorno da viagem.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Melina',
            'titulo': 'Qual é o prazo para aprovação de campanhas?',
            'pergunta': 'Gostaria de saber com quanto tempo de antecedência devemos enviar campanhas internas para aprovação.',
            'respostas': [
                ('Anabelle', 'O ideal é enviar a campanha com pelo menos três dias úteis de antecedência.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Dario',
            'titulo': 'Onde encontro o modelo atualizado de contrato?',
            'pergunta': 'Preciso elaborar um contrato novo com fornecedor e quero usar o modelo jurídico mais recente.',
            'respostas': [
                ('Arthur Clemente', 'O modelo atualizado está na pasta compartilhada do Jurídico, dentro de Modelos Oficiais.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Bianca',
            'titulo': 'Como abrir chamado para troca de equipamento?',
            'pergunta': 'Meu notebook está apresentando travamentos frequentes. Qual procedimento devo seguir para solicitar troca?',
            'respostas': [
                ('Arthur Clemente', 'Abra um chamado de infraestrutura informando patrimônio, sintomas e urgência operacional.'),
                ('Nicolas', 'Passei por isso recentemente e anexar prints do erro ajudou bastante na triagem.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Nicolas',
            'titulo': 'Quem aprova compra de material de escritório?',
            'pergunta': 'O setor precisa repor materiais básicos. Quem deve aprovar a compra antes do pedido ao fornecedor?',
            'respostas': [
                ('Valerio', 'A aprovação inicial é do gestor da área. Depois disso, o Financeiro valida orçamento e centro de custo.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Clara',
            'titulo': 'Como atualizar dados bancários no sistema?',
            'pergunta': 'Troquei de banco recentemente e preciso atualizar os dados para pagamento. Onde faço essa alteração?',
            'respostas': [
                ('Anabelle', 'Envie a solicitação ao RH com comprovante bancário em seu nome para validação.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Otavio',
            'titulo': 'Qual política para trabalho remoto eventual?',
            'pergunta': 'Existe uma regra específica para solicitar home office em situações pontuais durante a semana?',
            'respostas': [
                ('Anabelle', 'Sim. O pedido deve ser combinado com a liderança direta e registrado no sistema de presença.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Valerio',
            'titulo': 'Como pedir acesso ao painel de indicadores?',
            'pergunta': 'Preciso consultar indicadores de desempenho da área, mas ainda não tenho acesso ao painel corporativo.',
            'respostas': [
                ('Bianca', 'Solicite acesso pelo chamado de sistemas e informe quais painéis são necessários para sua função.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Melina',
            'titulo': 'Existe padrão para assinatura de e-mail?',
            'pergunta': 'Quero atualizar minha assinatura e preciso saber se existe um modelo institucional obrigatório.',
            'respostas': [
                ('Arthur Clemente', 'Sim. O modelo oficial fica na intranet, na seção Comunicação Interna.'),
                ('Melina', 'Encontrei o modelo e funcionou corretamente. Obrigada pelo retorno.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Dario',
            'titulo': 'Como reportar incidente de segurança da informação?',
            'pergunta': 'Recebi um e-mail suspeito pedindo dados internos. Qual canal devo usar para reportar esse incidente?',
            'respostas': [
                ('Bianca', 'Encaminhe o e-mail como anexo para Segurança da Informação e não clique em nenhum link.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Bianca',
            'titulo': 'Quem libera acesso de visitante ao prédio?',
            'pergunta': 'Receberemos um fornecedor amanhã e preciso entender como liberar a entrada com antecedência.',
            'respostas': [
                ('Clara', 'O cadastro deve ser enviado à recepção com nome completo, documento e horário previsto.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Nicolas',
            'titulo': 'Como solicitar alteração de centro de custo?',
            'pergunta': 'Um lançamento foi registrado no centro de custo incorreto. Como faço a correção?',
            'respostas': [
                ('Valerio', 'Abra uma solicitação financeira informando o lançamento, o centro atual e o centro correto.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Clara',
            'titulo': 'Onde consultar calendário de treinamentos?',
            'pergunta': 'Gostaria de ver os próximos treinamentos obrigatórios e opcionais disponíveis para minha área.',
            'respostas': [
                ('Anabelle', 'O calendário fica na intranet, na página de Desenvolvimento e Treinamentos.'),
            ],
        },
        {
            'status': 'fechada',
            'autor': 'Otavio',
            'titulo': 'Como funciona a solicitação de férias?',
            'pergunta': 'Quero programar minhas férias do próximo trimestre. Qual é o procedimento oficial para solicitar aprovação?',
            'respostas': [
                ('Anabelle', 'A solicitação deve ser feita no sistema de RH com pelo menos trinta dias de antecedência.'),
            ],
        },
        {
            'status': 'respondida',
            'autor': 'Valerio',
            'titulo': 'Qual canal para dúvidas sobre folha de pagamento?',
            'pergunta': 'Tenho uma dúvida sobre desconto em folha e gostaria de saber qual canal devo procurar.',
            'respostas': [
                ('Anabelle', 'Você pode abrir um atendimento pelo portal do RH ou falar com Benefícios em horário comercial.'),
            ],
        },
        {
            'status': 'respondida',
            'autor': 'Melina',
            'titulo': 'Como solicitar arte para comunicado interno?',
            'pergunta': 'Preciso de uma arte para divulgar uma iniciativa da área. Existe um fluxo específico para esse pedido?',
            'respostas': [
                ('Melina', 'O pedido deve entrar pelo formulário de Comunicação, com briefing, prazo e público-alvo.'),
                ('Arthur Clemente', 'Inclua também dimensões e canais onde a peça será publicada.'),
            ],
        },
        {
            'status': 'aberta',
            'autor': 'Dario',
            'titulo': 'Quem valida novos fornecedores estratégicos?',
            'pergunta': 'Estamos avaliando um novo fornecedor estratégico e preciso entender quem participa da validação inicial.',
            'respostas': [],
        },
        {
            'status': 'aberta',
            'autor': 'Bianca',
            'titulo': 'Existe previsão para atualização do sistema interno?',
            'pergunta': 'Alguns usuários perguntaram sobre melhorias no sistema interno. Existe uma data prevista para atualização?',
            'respostas': [],
        },
        {
            'status': 'aberta',
            'autor': 'Nicolas',
            'titulo': 'Como revisar solicitação de compra reaberta?',
            'pergunta': 'A solicitação de compra foi encerrada, mas surgiram novas informações do fornecedor. Como devemos prosseguir?',
            'motivo_reabertura': 'O fornecedor enviou uma proposta revisada com prazo menor e impacto financeiro relevante.',
            'reaberta_por': 'Clara',
            'respostas': [
                ('Valerio', 'Antes de seguir, compare a nova proposta com o orçamento aprovado anteriormente.'),
            ],
        },
        {
            'status': 'aberta',
            'autor': 'Clara',
            'titulo': 'Podemos reabrir discussão sobre benefício flexível?',
            'pergunta': 'A dúvida havia sido encerrada, mas recebemos novas perguntas sobre regras de uso do benefício flexível.',
            'motivo_reabertura': 'Novas dúvidas surgiram após a comunicação oficial enviada para toda a empresa.',
            'reaberta_por': 'Otavio',
            'respostas': [
                ('Anabelle', 'Podemos reavaliar os pontos e complementar a comunicação com exemplos práticos.'),
                ('Dario', 'Recomendo validar os exemplos com o Jurídico antes da nova publicação.'),
            ],
        },
    ]
    usuarios_demo = [
        {
            'username': 'arthur',
            'first_name': 'Arthur Clemente',
            'email': 'arthur@gmail.com',
            'departamento': 'ti',
            'is_staff': True,
            'is_superuser': True,
        },
        {
            'username': 'anabelle',
            'first_name': 'Anabelle',
            'email': 'anabelle@gmail.com',
            'departamento': 'rh',
            'is_staff': True,
            'is_superuser': False,
        },
        {
            'username': 'valerio',
            'first_name': 'Valerio',
            'email': 'valerio@gmail.com',
            'departamento': 'fin',
            'is_staff': False,
            'is_superuser': False,
        },
        {
            'username': 'melina',
            'first_name': 'Melina',
            'email': 'melina@gmail.com',
            'departamento': 'ma',
            'is_staff': False,
            'is_superuser': False,
        },
        {
            'username': 'dario',
            'first_name': 'Dario',
            'email': 'dario@gmail.com',
            'departamento': 'jur',
            'is_staff': False,
            'is_superuser': False,
        },
        {
            'username': 'bianca',
            'first_name': 'Bianca',
            'email': 'bianca@gmail.com',
            'departamento': 'ti',
            'is_staff': False,
            'is_superuser': False,
        },
        {
            'username': 'nicolas',
            'first_name': 'Nicolas',
            'email': 'nicolas@gmail.com',
            'departamento': 'ou',
            'is_staff': False,
            'is_superuser': False,
        },
        {
            'username': 'clara',
            'first_name': 'Clara',
            'email': 'clara@gmail.com',
            'departamento': 'rh',
            'is_staff': False,
            'is_superuser': False,
        },
        {
            'username': 'otavio',
            'first_name': 'Otavio',
            'email': 'otavio@gmail.com',
            'departamento': 'fin',
            'is_staff': False,
            'is_superuser': False,
        },
    ]

    @transaction.atomic
    def handle(self, *args, **options):
        usuarios = self.criar_usuarios()
        self.recriar_perguntas(usuarios)
        self.recriar_tokens(usuarios)
        self.stdout.write(self.style.SUCCESS('Demonstração criada com sucesso.'))

    def criar_usuarios(self):
        usuarios = {}
        for dados in self.usuarios_demo:
            user, _ = User.objects.get_or_create(username=dados['username'])
            user.first_name = dados['first_name']
            user.email = dados['email']
            user.is_staff = dados['is_staff']
            user.is_superuser = dados['is_superuser']
            user.is_active = True
            user.set_password(self.senha_padrao)
            user.save()
            Perfil.objects.update_or_create(usuario=user, defaults={ 'departamento': dados['departamento'] })
            usuarios[user.first_name] = user
            usuarios[user.username] = user
        return usuarios

    def recriar_perguntas(self, usuarios):
        titulos = [item['titulo'] for item in self.perguntas_demo]
        Pergunta.objects.filter(titulo__in=titulos).delete()
        agora = timezone.now()
        for indice, dados in enumerate(self.perguntas_demo):
            pergunta = Pergunta.objects.create(
                autor=usuarios[dados['autor']],
                titulo=dados['titulo'],
                pergunta=dados['pergunta'],
                status=dados['status'],
            )
            criado_em = agora - timedelta(days=20 - indice, hours=indice % 6)
            campos_update = {'criado_em': criado_em}
            if dados.get('motivo_reabertura'):
                campos_update.update({
                    'motivo_reabertura': dados['motivo_reabertura'],
                    'reaberta_em': criado_em + timedelta(hours=6),
                    'reaberta_por': usuarios[dados['reaberta_por']],
                })
            Pergunta.objects.filter(pk=pergunta.pk).update(**campos_update)
            pergunta.refresh_from_db()
            for posicao, (autor, texto) in enumerate(dados['respostas']):
                resposta = Resposta.objects.create(autor=usuarios[autor], pergunta=pergunta, resposta=texto)
                Resposta.objects.filter(pk=resposta.pk).update(criado_em=pergunta.criado_em + timedelta(hours=posicao + 1))

    def recriar_tokens(self, usuarios):
        StaffToken.objects.filter(descricao__startswith='Demonstração:').delete()
        token_usado, _ = StaffToken.criar(criado_por=usuarios['Arthur Clemente'], descricao='Nova moderadora: Anabelle')
        token_usado.ativo = False
        token_usado.usado_por = usuarios['Anabelle']
        token_usado.usado_em = timezone.now() - timedelta(days=2, hours=3)
        token_usado.save(update_fields=['ativo', 'usado_por', 'usado_em'])
        token_revogado, _ = StaffToken.criar(criado_por=usuarios['Arthur Clemente'], descricao='Novo moderador: Dario')
        token_revogado.ativo = False
        token_revogado.save(update_fields=['ativo'])
