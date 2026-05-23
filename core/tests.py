from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import (
    FormAdminUsuario,
    FormCadastro,
    FormPerfil,
    FormPergunta,
    FormResposta,
    FormStaffToken,
)
from .models import Perfil, Pergunta, Resposta, StaffToken
from .views import (
    administrador,
    dentro_do_prazo,
    moderador,
    pode_editar,
    pode_excluir,
    pode_fechar,
)


TEST_PASSWORD = "SenhaForte123!"
FAST_PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def texto(tamanho=40):
    return "x" * tamanho


class BaseCoreTestCase(TestCase):
    def criar_usuario(
        self,
        username="usuario1",
        email=None,
        first_name="Usuário Teste",
        departamento="ti",
        password=TEST_PASSWORD,
        is_staff=False,
        is_superuser=False,
        is_active=True,
    ):
        user = User.objects.create_user(
            username=username,
            email=email or f"{username}@gmail.com",
            password=password,
            first_name=first_name,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=is_active,
        )
        Perfil.objects.create(usuario=user, departamento=departamento)
        return user

    def criar_pergunta(
        self,
        autor=None,
        titulo="Título de pergunta válido",
        pergunta="Texto da pergunta com tamanho suficiente.",
        status="aberta",
        criado_em=None,
        motivo_reabertura="",
        reaberta_por=None,
        reaberta_em=None,
    ):
        autor = autor or self.criar_usuario(username="autor1")
        obj = Pergunta.objects.create(
            autor=autor,
            titulo=titulo,
            pergunta=pergunta,
            status=status,
            motivo_reabertura=motivo_reabertura,
            reaberta_por=reaberta_por,
            reaberta_em=reaberta_em,
        )
        updates = {}
        if criado_em is not None:
            updates["criado_em"] = criado_em
        if reaberta_em is not None:
            updates["reaberta_em"] = reaberta_em
        if updates:
            Pergunta.objects.filter(pk=obj.pk).update(**updates)
            obj.refresh_from_db()
        return obj

    def criar_resposta(
        self,
        pergunta,
        autor=None,
        resposta="Resposta com tamanho suficiente.",
        criado_em=None,
    ):
        autor = autor or pergunta.autor
        obj = Resposta.objects.create(autor=autor, pergunta=pergunta, resposta=resposta)
        if criado_em is not None:
            Resposta.objects.filter(pk=obj.pk).update(criado_em=criado_em)
            obj.refresh_from_db()
        return obj

    def mensagens(self, response):
        return [str(message) for message in get_messages(response.wsgi_request)]


class ModelTests(BaseCoreTestCase):
    def test_perfil_str_usa_usuario_e_departamento(self):
        user = self.criar_usuario(username="maria", departamento="rh")

        self.assertEqual(str(user.perfil), "maria – rh")

    def test_pergunta_defaults_ordering_e_str(self):
        user = self.criar_usuario(username="autor")
        primeira = self.criar_pergunta(autor=user, titulo="Primeira pergunta válida")
        segunda = self.criar_pergunta(autor=user, titulo="Segunda pergunta válida")

        self.assertEqual(primeira.status, "aberta")
        self.assertEqual(str(primeira), "Primeira pergunta válida")

    def test_resposta_ordering_e_str(self):
        user = self.criar_usuario(username="autor", first_name="Autor Nome")
        pergunta = self.criar_pergunta(autor=user)
        antiga = self.criar_resposta(
            pergunta,
            resposta="Resposta mais antiga válida.",
            criado_em=timezone.now() - timedelta(hours=2),
        )
        nova = self.criar_resposta(
            pergunta,
            resposta="Resposta mais nova válida.",
            criado_em=timezone.now() - timedelta(hours=1),
        )

        self.assertEqual(str(antiga), "Resposta de Autor Nome para 'Título de pergunta válido'")
        self.assertEqual(list(pergunta.respostas.values_list("pk", flat=True)), [antiga.pk, nova.pk])

    def test_validadores_de_tamanho_dos_modelos(self):
        user = self.criar_usuario(username="autor")
        pergunta = Pergunta(autor=user, titulo="curto", pergunta="curta")
        resposta = Resposta(autor=user, pergunta=self.criar_pergunta(autor=user), resposta="curta")

        with self.assertRaises(ValidationError):
            pergunta.full_clean()
        with self.assertRaises(ValidationError):
            resposta.full_clean()

    def test_excluir_usuario_remove_perfil_perguntas_e_respostas_por_cascade(self):
        user = self.criar_usuario(username="autor")
        pergunta = self.criar_pergunta(autor=user)
        self.criar_resposta(pergunta=pergunta, autor=user)

        user.delete()

        self.assertEqual(Perfil.objects.count(), 0)
        self.assertEqual(Pergunta.objects.count(), 0)
        self.assertEqual(Resposta.objects.count(), 0)

    def test_staff_token_criar_valido_hash_prefixo_e_str(self):
        admin = self.criar_usuario(username="admin", is_staff=True)

        token, codigo = StaffToken.criar(admin, descricao="Token para moderador")

        self.assertTrue(token.ativo)
        self.assertEqual(token.criado_por, admin)
        self.assertEqual(token.prefixo, codigo[:12])
        self.assertEqual(token.token_hash, StaffToken.hashear(codigo))
        self.assertNotEqual(token.token_hash, codigo)
        self.assertEqual(StaffToken.valido(codigo), token)
        self.assertEqual(str(token), f"{token.prefixo}... (ativo)")

    def test_staff_token_consumir_promove_usuario_e_invalida_codigo(self):
        admin = self.criar_usuario(username="admin", is_staff=True)
        usuario = self.criar_usuario(username="comum", is_staff=False)
        token, codigo = StaffToken.criar(admin)

        consumido = StaffToken.consumir(f"  {codigo}  ", usuario)
        usuario.refresh_from_db()
        token.refresh_from_db()

        self.assertTrue(consumido)
        self.assertTrue(usuario.is_staff)
        self.assertFalse(token.ativo)
        self.assertEqual(token.usado_por, usuario)
        self.assertIsNotNone(token.usado_em)
        self.assertIsNone(StaffToken.valido(codigo))
        self.assertFalse(StaffToken.consumir(codigo, usuario))
        self.assertEqual(str(token), f"{token.prefixo}... (usado)")

    def test_staff_token_valido_rejeita_codigo_vazio_revogado_ou_usado(self):
        admin = self.criar_usuario(username="admin", is_staff=True)
        usuario = self.criar_usuario(username="comum")
        ativo, codigo_ativo = StaffToken.criar(admin)
        revogado, codigo_revogado = StaffToken.criar(admin)
        usado, codigo_usado = StaffToken.criar(admin)
        revogado.ativo = False
        revogado.save(update_fields=["ativo"])
        usado.ativo = False
        usado.usado_por = usuario
        usado.usado_em = timezone.now()
        usado.save(update_fields=["ativo", "usado_por", "usado_em"])

        self.assertEqual(StaffToken.valido(codigo_ativo), ativo)
        self.assertIsNone(StaffToken.valido(""))
        self.assertIsNone(StaffToken.valido("codigo-inexistente"))
        self.assertIsNone(StaffToken.valido(codigo_revogado))
        self.assertIsNone(StaffToken.valido(codigo_usado))


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class FormCadastroTests(BaseCoreTestCase):
    def dados_validos(self, **overrides):
        data = {
            "username": "novousuario",
            "email": "novo@gmail.com",
            "first_name": "Novo Usuário",
            "departamento": "ti",
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
            "staff_token": "",
        }
        data.update(overrides)
        return data

    def test_cadastro_valido_cria_usuario_com_senha_hash_e_perfil(self):
        form = FormCadastro(data=self.dados_validos())

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertEqual(user.username, "novousuario")
        self.assertEqual(user.email, "novo@gmail.com")
        self.assertTrue(user.check_password(TEST_PASSWORD))
        self.assertNotEqual(user.password, TEST_PASSWORD)
        self.assertEqual(user.perfil.departamento, "ti")
        self.assertFalse(user.is_staff)

    def test_cadastro_com_token_valido_promove_para_staff_e_consumir_token(self):
        admin = self.criar_usuario(username="admin", is_staff=True)
        token, codigo = StaffToken.criar(admin)
        form = FormCadastro(data=self.dados_validos(staff_token=f"  {codigo}  "))

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        token.refresh_from_db()

        self.assertTrue(user.is_staff)
        self.assertFalse(token.ativo)
        self.assertEqual(token.usado_por, user)
        self.assertIsNotNone(token.usado_em)

    def test_cadastro_rejeita_email_fora_do_gmail(self):
        form = FormCadastro(data=self.dados_validos(email="novo@example.com"))

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_cadastro_rejeita_email_duplicado(self):
        self.criar_usuario(username="existente", email="novo@gmail.com")
        form = FormCadastro(data=self.dados_validos())

        self.assertFalse(form.is_valid())
        self.assertIn("Este e-mail já está em uso.", form.errors["email"])

    def test_cadastro_rejeita_username_curto(self):
        form = FormCadastro(data=self.dados_validos(username="abc"))

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_cadastro_rejeita_senhas_diferentes(self):
        form = FormCadastro(data=self.dados_validos(password_confirm="OutraSenha123!"))

        self.assertFalse(form.is_valid())
        self.assertIn("password_confirm", form.errors)

    def test_cadastro_rejeita_senha_fraca(self):
        form = FormCadastro(data=self.dados_validos(password="123", password_confirm="123"))

        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_cadastro_rejeita_staff_token_invalido(self):
        form = FormCadastro(data=self.dados_validos(staff_token="codigo-invalido"))

        self.assertFalse(form.is_valid())
        self.assertIn("staff_token", form.errors)

    def test_cadastro_commit_false_nao_salva_usuario_nem_perfil(self):
        form = FormCadastro(data=self.dados_validos())

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)

        self.assertIsNone(user.pk)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Perfil.objects.count(), 0)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class FormPerfilTests(BaseCoreTestCase):
    def dados_validos(self, user, **overrides):
        data = {
            "email": user.email,
            "first_name": user.first_name,
            "departamento": user.perfil.departamento,
            "staff_token": "",
        }
        data.update(overrides)
        return data

    def test_perfil_inicializa_departamento_do_usuario(self):
        user = self.criar_usuario(username="ana", departamento="rh")

        form = FormPerfil(instance=user)

        self.assertEqual(form.fields["departamento"].initial, "rh")

    def test_perfil_atualiza_dados_e_departamento(self):
        user = self.criar_usuario(username="ana", departamento="rh")
        form = FormPerfil(
            data=self.dados_validos(
                user,
                email="ana.novo@gmail.com",
                first_name="Ana Atualizada",
                departamento="fin",
            ),
            instance=user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user.refresh_from_db()

        self.assertEqual(user.email, "ana.novo@gmail.com")
        self.assertEqual(user.first_name, "Ana Atualizada")
        self.assertEqual(user.perfil.departamento, "fin")

    def test_perfil_consumir_token_promove_usuario_comum(self):
        admin = self.criar_usuario(username="admin", is_staff=True)
        user = self.criar_usuario(username="ana", is_staff=False)
        token, codigo = StaffToken.criar(admin)
        form = FormPerfil(data=self.dados_validos(user, staff_token=codigo), instance=user)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user.refresh_from_db()
        token.refresh_from_db()

        self.assertTrue(user.is_staff)
        self.assertFalse(token.ativo)
        self.assertEqual(token.usado_por, user)

    def test_perfil_rejeita_email_fora_do_gmail(self):
        user = self.criar_usuario(username="ana")
        form = FormPerfil(data=self.dados_validos(user, email="ana@example.com"), instance=user)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_perfil_rejeita_email_de_outro_usuario(self):
        user = self.criar_usuario(username="ana")
        outro = self.criar_usuario(username="bruno", email="bruno@gmail.com")
        form = FormPerfil(data=self.dados_validos(user, email=outro.email), instance=user)

        self.assertFalse(form.is_valid())
        self.assertIn("Este e-mail já está em uso.", form.errors["email"])

    def test_perfil_aceita_manter_o_proprio_email(self):
        user = self.criar_usuario(username="ana", email="ana@gmail.com")
        form = FormPerfil(data=self.dados_validos(user), instance=user)

        self.assertTrue(form.is_valid(), form.errors)

    def test_perfil_rejeita_first_name_curto(self):
        user = self.criar_usuario(username="ana")
        form = FormPerfil(data=self.dados_validos(user, first_name="An"), instance=user)

        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)

    def test_perfil_rejeita_token_invalido(self):
        user = self.criar_usuario(username="ana")
        form = FormPerfil(data=self.dados_validos(user, staff_token="codigo-invalido"), instance=user)

        self.assertFalse(form.is_valid())
        self.assertIn("staff_token", form.errors)

    def test_perfil_rejeita_token_quando_usuario_ja_e_staff(self):
        admin = self.criar_usuario(username="admin", is_staff=True)
        user = self.criar_usuario(username="ana", is_staff=True)
        _, codigo = StaffToken.criar(admin)
        form = FormPerfil(data=self.dados_validos(user, staff_token=codigo), instance=user)

        self.assertFalse(form.is_valid())
        self.assertIn("Você já possui permissão de moderador.", form.errors["staff_token"])


class FormPerguntaRespostaAdminTokenTests(BaseCoreTestCase):
    def test_form_pergunta_valido(self):
        form = FormPergunta(data={"titulo": "Título completo", "pergunta": "Pergunta com texto suficiente."})

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_pergunta_rejeita_titulo_duplicado_normalizado(self):
        autor = self.criar_usuario(username="autor")
        existente = self.criar_pergunta(autor=autor, titulo="Ética e Compliance Interno")
        form = FormPergunta(data={"titulo": " etica e compliance interno ", "pergunta": "Pergunta com texto suficiente."})

        self.assertFalse(form.is_valid())
        self.assertIn(f"PERGUNTA_EXISTENTE:{existente.pk}", form.non_field_errors())

    def test_form_pergunta_ignora_a_propria_instancia_ao_editar(self):
        autor = self.criar_usuario(username="autor")
        pergunta = self.criar_pergunta(autor=autor, titulo="Título Original Válido")
        form = FormPergunta(
            data={"titulo": "titulo original valido", "pergunta": "Pergunta atualizada suficiente."},
            instance=pergunta,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_pergunta_rejeita_textos_curtos(self):
        form = FormPergunta(data={"titulo": "curto", "pergunta": "curta"})

        self.assertFalse(form.is_valid())
        self.assertIn("titulo", form.errors)
        self.assertIn("pergunta", form.errors)

    def test_form_resposta_valido_e_invalido(self):
        valido = FormResposta(data={"resposta": "Resposta com tamanho válido."})
        invalido = FormResposta(data={"resposta": "curta"})

        self.assertTrue(valido.is_valid(), valido.errors)
        self.assertFalse(invalido.is_valid())
        self.assertIn("resposta", invalido.errors)

    def test_form_staff_token_descricao_opcional_mas_com_minimo_quando_informada(self):
        vazio = FormStaffToken(data={"descricao": ""})
        curta = FormStaffToken(data={"descricao": "curta"})
        valida = FormStaffToken(data={"descricao": "Convite para novo moderador"})

        self.assertTrue(vazio.is_valid(), vazio.errors)
        self.assertFalse(curta.is_valid())
        self.assertTrue(valida.is_valid(), valida.errors)

    def test_form_admin_usuario_valida_campos(self):
        valido = FormAdminUsuario(data={"usuario": 1, "first_name": "Maria", "departamento": "jur"})
        sem_apelido = FormAdminUsuario(data={"usuario": 1, "first_name": "Ma", "departamento": "jur"})
        departamento_invalido = FormAdminUsuario(data={"usuario": 1, "first_name": "Maria", "departamento": "xxx"})

        self.assertTrue(valido.is_valid(), valido.errors)
        self.assertFalse(sem_apelido.is_valid())
        self.assertFalse(departamento_invalido.is_valid())


class PermissionHelperTests(BaseCoreTestCase):
    def test_administrador_e_moderador(self):
        anonimo = AnonymousUser()
        comum = self.criar_usuario(username="comum")
        staff = self.criar_usuario(username="staff", is_staff=True)
        admin = self.criar_usuario(username="admin", is_superuser=True)

        self.assertFalse(administrador(anonimo))
        self.assertFalse(administrador(comum))
        self.assertFalse(moderador(comum))
        self.assertTrue(moderador(staff))
        self.assertTrue(administrador(admin))
        self.assertTrue(moderador(admin))

    def test_dentro_do_prazo(self):
        user = self.criar_usuario(username="autor")
        recente = self.criar_pergunta(autor=user, criado_em=timezone.now() - timedelta(hours=23))
        antiga = self.criar_pergunta(autor=user, titulo="Pergunta antiga válida", criado_em=timezone.now() - timedelta(days=2))

        self.assertTrue(dentro_do_prazo(recente))
        self.assertFalse(dentro_do_prazo(antiga))

    def test_pode_editar_apenas_autor_dentro_do_prazo(self):
        autor = self.criar_usuario(username="autor")
        outro = self.criar_usuario(username="outro")
        recente = self.criar_pergunta(autor=autor, criado_em=timezone.now() - timedelta(hours=1))
        antiga = self.criar_pergunta(autor=autor, titulo="Pergunta antiga válida", criado_em=timezone.now() - timedelta(days=2))

        self.assertTrue(pode_editar(recente, autor))
        self.assertFalse(pode_editar(recente, outro))
        self.assertFalse(pode_editar(antiga, autor))

    def test_pode_excluir_moderador_ou_autor_no_prazo(self):
        autor = self.criar_usuario(username="autor")
        outro = self.criar_usuario(username="outro")
        staff = self.criar_usuario(username="staff", is_staff=True)
        antiga = self.criar_pergunta(autor=autor, criado_em=timezone.now() - timedelta(days=2))

        self.assertTrue(pode_excluir(antiga, staff))
        self.assertFalse(pode_excluir(antiga, autor))
        self.assertFalse(pode_excluir(antiga, outro))

    def test_pode_fechar_autor_moderador_ou_usuario_que_reabriu(self):
        autor = self.criar_usuario(username="autor")
        reabriu = self.criar_usuario(username="reabriu")
        outro = self.criar_usuario(username="outro")
        staff = self.criar_usuario(username="staff", is_staff=True)
        normal = self.criar_pergunta(autor=autor)
        reaberta = self.criar_pergunta(
            autor=autor,
            titulo="Pergunta reaberta válida",
            reaberta_por=reabriu,
            reaberta_em=timezone.now(),
        )

        self.assertTrue(pode_fechar(normal, autor))
        self.assertTrue(pode_fechar(normal, staff))
        self.assertFalse(pode_fechar(normal, outro))
        self.assertTrue(pode_fechar(reaberta, reabriu))
        self.assertTrue(pode_fechar(reaberta, staff))
        self.assertFalse(pode_fechar(reaberta, autor))


@override_settings(ROOT_URLCONF="core.urls", PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class AutenticacaoViewTests(BaseCoreTestCase):
    def test_usuario_anonimo_e_redirecionado_para_autenticacao(self):
        response = self.client.get(reverse("listagem"))

        self.assertRedirects(response, f'{reverse("autenticacao")}?next={reverse("listagem")}')

    def test_get_autenticacao_renderiza_forms(self):
        response = self.client.get(reverse("autenticacao"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("form_login", response.context)
        self.assertIn("form_cadastro", response.context)

    def test_autenticacao_redireciona_usuario_logado(self):
        user = self.criar_usuario(username="logado")
        self.client.force_login(user)

        response = self.client.get(reverse("autenticacao"))

        self.assertRedirects(response, reverse("listagem"))

    def test_cadastro_pela_view_cria_usuario_perfil_e_autentica(self):
        response = self.client.post(
            reverse("autenticacao"),
            {
                "acao": "cadastro",
                "username": "novousuario",
                "email": "novo@gmail.com",
                "first_name": "Novo Usuário",
                "departamento": "ti",
                "password": TEST_PASSWORD,
                "password_confirm": TEST_PASSWORD,
                "staff_token": "",
            },
        )

        user = User.objects.get(username="novousuario")
        self.assertRedirects(response, reverse("listagem"))
        self.assertEqual(user.perfil.departamento, "ti")
        self.assertTrue(user.check_password(TEST_PASSWORD))

    def test_login_sucesso_e_falha(self):
        self.criar_usuario(username="usuario", password=TEST_PASSWORD)

        sucesso = self.client.post(reverse("autenticacao"), {"acao": "login", "username": "usuario", "password": TEST_PASSWORD})
        self.assertRedirects(sucesso, reverse("listagem"))
        self.client.logout()

        falha = self.client.post(reverse("autenticacao"), {"acao": "login", "username": "usuario", "password": "errada"})
        self.assertEqual(falha.status_code, 200)

    def test_sair_faz_logout(self):
        user = self.criar_usuario(username="usuario")
        self.client.force_login(user)

        response = self.client.get(reverse("sair"))

        self.assertRedirects(response, reverse("autenticacao"))
        response = self.client.get(reverse("listagem"))
        self.assertEqual(response.status_code, 302)


@override_settings(ROOT_URLCONF="core.urls", PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class PerguntaListagemViewTests(BaseCoreTestCase):
    def setUp(self):
        self.user = self.criar_usuario(username="autor", first_name="Autor Principal")
        self.client.force_login(self.user)

    def test_listagem_filtra_por_busca_no_titulo_e_status(self):
        self.criar_pergunta(autor=self.user, titulo="Como configurar VPN corporativa", status="aberta")
        self.criar_pergunta(autor=self.user, titulo="Como pedir reembolso", status="fechada")

        response = self.client.get(reverse("listagem"), {"busca": "VPN", "status": "aberta"})

        self.assertEqual(response.status_code, 200)
        titulos = [pergunta.titulo for pergunta in response.context["perguntas"]]
        self.assertEqual(titulos, ["Como configurar VPN corporativa"])
        self.assertEqual(response.context["busca"], "VPN")
        self.assertEqual(response.context["status_filtro"], "aberta")

    def test_listagem_filtra_por_nome_do_autor(self):
        outro = self.criar_usuario(username="outro", first_name="Pessoa Encontrada")
        encontrada = self.criar_pergunta(autor=outro, titulo="Pergunta do outro autor")
        self.criar_pergunta(autor=self.user, titulo="Pergunta do autor logado")

        response = self.client.get(reverse("listagem"), {"busca": "Encontrada"})

        self.assertEqual(list(response.context["perguntas"]), [encontrada])

    def test_criar_pergunta_pela_view(self):
        response = self.client.post(
            reverse("perguntar"),
            {"titulo": "Como acessar ambiente interno?", "pergunta": "Preciso acessar o ambiente interno da empresa."},
        )
        pergunta = Pergunta.objects.get(titulo="Como acessar ambiente interno?")

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertEqual(pergunta.autor, self.user)
        self.assertEqual(pergunta.status, "aberta")

    def test_criar_pergunta_duplicada_expoe_id_da_existente(self):
        existente = self.criar_pergunta(autor=self.user, titulo="Política de Home Office")

        response = self.client.post(
            reverse("perguntar"),
            {"titulo": "politica de home office", "pergunta": "Pergunta com texto suficiente."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pergunta_existente_id"], str(existente.pk))
        self.assertEqual(Pergunta.objects.filter(titulo__icontains="home").count(), 1)

    def test_editar_pergunta_dentro_do_prazo(self):
        pergunta = self.criar_pergunta(autor=self.user)

        response = self.client.post(
            reverse("editar_pergunta", args=[pergunta.pk]),
            {"titulo": "Título alterado válido", "pergunta": "Texto alterado com tamanho suficiente."},
        )
        pergunta.refresh_from_db()

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertEqual(pergunta.titulo, "Título alterado válido")
        self.assertEqual(pergunta.pergunta, "Texto alterado com tamanho suficiente.")

    def test_nao_edita_pergunta_fechada_antiga_ou_reaberta(self):
        fechada = self.criar_pergunta(autor=self.user, titulo="Pergunta fechada válida", status="fechada")
        antiga = self.criar_pergunta(autor=self.user, titulo="Pergunta antiga válida", criado_em=timezone.now() - timedelta(days=2))
        reaberta = self.criar_pergunta(
            autor=self.user,
            titulo="Pergunta reaberta válida",
            motivo_reabertura="Motivo suficiente para reabrir",
            reaberta_por=self.user,
            reaberta_em=timezone.now(),
        )

        for pergunta in [fechada, antiga, reaberta]:
            response = self.client.get(reverse("editar_pergunta", args=[pergunta.pk]))
            self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))


@override_settings(ROOT_URLCONF="core.urls", PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class DetalhesViewTests(BaseCoreTestCase):
    def setUp(self):
        self.autor = self.criar_usuario(username="autor", first_name="Autor")
        self.outro = self.criar_usuario(username="outro", first_name="Outro")
        self.staff = self.criar_usuario(username="staff", first_name="Staff", is_staff=True)

    def test_detalhes_marca_permissoes_das_respostas(self):
        pergunta = self.criar_pergunta(autor=self.autor)
        resposta = self.criar_resposta(pergunta, autor=self.autor)
        self.client.force_login(self.autor)

        response = self.client.get(reverse("detalhes", args=[pergunta.pk]))

        self.assertEqual(response.status_code, 200)
        resposta_contexto = list(response.context["respostas"])[0]
        self.assertEqual(resposta_contexto.pk, resposta.pk)
        self.assertTrue(resposta_contexto.pode_editar)
        self.assertTrue(resposta_contexto.pode_excluir)
        self.assertTrue(response.context["pode_editar_pergunta"])
        self.assertTrue(response.context["pode_excluir_pergunta"])

    def test_responder_pergunta_aberta_cria_resposta_e_marca_como_respondida(self):
        pergunta = self.criar_pergunta(autor=self.autor)
        self.client.force_login(self.outro)

        response = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "responder", "resposta": "Resposta enviada com tamanho suficiente."},
        )
        pergunta.refresh_from_db()

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertEqual(pergunta.status, "respondida")
        self.assertTrue(pergunta.respostas.filter(autor=self.outro).exists())

    def test_nao_responde_pergunta_fechada(self):
        pergunta = self.criar_pergunta(autor=self.autor, status="fechada")
        self.client.force_login(self.outro)

        response = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "responder", "resposta": "Resposta enviada com tamanho suficiente."},
        )

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertFalse(pergunta.respostas.exists())

    def test_fechar_pergunta_exige_resposta(self):
        pergunta = self.criar_pergunta(autor=self.autor)
        self.client.force_login(self.autor)

        response = self.client.post(reverse("detalhes", args=[pergunta.pk]), {"acao": "fechar_pergunta"})
        pergunta.refresh_from_db()

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertEqual(pergunta.status, "aberta")
        self.assertIn("A pergunta precisa ter ao menos uma resposta para ser fechada.", self.mensagens(response))

    def test_autor_fecha_pergunta_respondida(self):
        pergunta = self.criar_pergunta(autor=self.autor, status="respondida")
        self.criar_resposta(pergunta, autor=self.outro)
        self.client.force_login(self.autor)

        response = self.client.post(reverse("detalhes", args=[pergunta.pk]), {"acao": "fechar_pergunta"})
        pergunta.refresh_from_db()

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertEqual(pergunta.status, "fechada")

    def test_pergunta_reaberta_so_pode_ser_fechada_por_moderador_ou_quem_reabriu(self):
        pergunta = self.criar_pergunta(
            autor=self.autor,
            status="aberta",
            reaberta_por=self.outro,
            reaberta_em=timezone.now(),
            motivo_reabertura="Motivo suficiente para reabrir",
        )
        self.criar_resposta(pergunta, autor=self.staff)

        self.client.force_login(self.autor)
        response = self.client.post(reverse("detalhes", args=[pergunta.pk]), {"acao": "fechar_pergunta"})
        pergunta.refresh_from_db()
        self.assertEqual(pergunta.status, "aberta")
        self.assertIn("Você não pode fechar esta pergunta.", self.mensagens(response))

        self.client.force_login(self.outro)
        response = self.client.post(reverse("detalhes", args=[pergunta.pk]), {"acao": "fechar_pergunta"})
        pergunta.refresh_from_db()
        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertEqual(pergunta.status, "fechada")

    def test_reabrir_pergunta_fechada_exige_motivo_suficiente(self):
        pergunta = self.criar_pergunta(autor=self.autor, status="fechada")
        self.client.force_login(self.outro)

        curto = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "reabrir_pergunta", "motivo_reabertura": "curto"},
        )
        pergunta.refresh_from_db()
        self.assertEqual(pergunta.status, "fechada")
        self.assertIn("Informe um motivo com ao menos 10 caracteres.", self.mensagens(curto))

        response = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "reabrir_pergunta", "motivo_reabertura": "Motivo realmente suficiente"},
        )
        pergunta.refresh_from_db()

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertEqual(pergunta.status, "aberta")
        self.assertEqual(pergunta.reaberta_por, self.outro)
        self.assertIsNotNone(pergunta.reaberta_em)

    def test_editar_e_salvar_resposta_do_autor_no_prazo(self):
        pergunta = self.criar_pergunta(autor=self.autor)
        resposta = self.criar_resposta(pergunta, autor=self.outro)
        self.client.force_login(self.outro)

        editar = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "editar_resposta", "resposta_id": resposta.pk},
        )
        self.assertEqual(editar.status_code, 200)
        self.assertEqual(editar.context["editando_id"], resposta.pk)

        salvar = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "salvar_resposta", "resposta_id": resposta.pk, "resposta": "Resposta alterada com tamanho suficiente."},
        )
        resposta.refresh_from_db()

        self.assertRedirects(salvar, reverse("detalhes", args=[pergunta.pk]))
        self.assertEqual(resposta.resposta, "Resposta alterada com tamanho suficiente.")

    def test_nao_edita_resposta_fora_do_prazo(self):
        pergunta = self.criar_pergunta(autor=self.autor)
        resposta = self.criar_resposta(pergunta, autor=self.outro, criado_em=timezone.now() - timedelta(days=2))
        self.client.force_login(self.outro)

        response = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "salvar_resposta", "resposta_id": resposta.pk, "resposta": "Resposta alterada com tamanho suficiente."},
        )
        resposta.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(resposta.resposta, "Resposta alterada com tamanho suficiente.")

    def test_excluir_ultima_resposta_reabre_pergunta_respondida(self):
        pergunta = self.criar_pergunta(autor=self.autor, status="respondida")
        resposta = self.criar_resposta(pergunta, autor=self.outro)
        self.client.force_login(self.outro)

        response = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "excluir_resposta", "resposta_id": resposta.pk},
        )
        pergunta.refresh_from_db()

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertFalse(Resposta.objects.filter(pk=resposta.pk).exists())
        self.assertEqual(pergunta.status, "aberta")

    def test_moderador_exclui_resposta_fechada(self):
        pergunta = self.criar_pergunta(autor=self.autor, status="fechada")
        resposta = self.criar_resposta(pergunta, autor=self.outro, criado_em=timezone.now() - timedelta(days=2))
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("detalhes", args=[pergunta.pk]),
            {"acao": "excluir_resposta", "resposta_id": resposta.pk},
        )
        pergunta.refresh_from_db()

        self.assertRedirects(response, reverse("detalhes", args=[pergunta.pk]))
        self.assertFalse(Resposta.objects.filter(pk=resposta.pk).exists())
        self.assertEqual(pergunta.status, "aberta")

    def test_autor_exclui_pergunta_aberta_no_prazo(self):
        pergunta = self.criar_pergunta(autor=self.autor)
        self.client.force_login(self.autor)

        response = self.client.post(reverse("detalhes", args=[pergunta.pk]), {"acao": "excluir_pergunta"})

        self.assertRedirects(response, reverse("listagem"))
        self.assertFalse(Pergunta.objects.filter(pk=pergunta.pk).exists())

    def test_usuario_comum_nao_exclui_pergunta_fechada(self):
        pergunta = self.criar_pergunta(autor=self.autor, status="fechada")
        self.client.force_login(self.autor)

        response = self.client.post(reverse("detalhes", args=[pergunta.pk]), {"acao": "excluir_pergunta"})

        self.assertTemplateUsed(response, "detalhes.html")
        self.assertTrue(Pergunta.objects.filter(pk=pergunta.pk).exists())
        self.assertIn("A pergunta não pode ser excluida quando fechada.", self.mensagens(response))


@override_settings(ROOT_URLCONF="core.urls", PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class PerfilViewTests(BaseCoreTestCase):
    def test_get_perfil_e_post_atualiza_usuario(self):
        user = self.criar_usuario(username="usuario", departamento="ti")
        self.client.force_login(user)

        get_response = self.client.get(reverse("perfil"))
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("form", get_response.context)

        response = self.client.post(
            reverse("perfil"),
            {
                "email": "usuario.novo@gmail.com",
                "first_name": "Usuário Novo",
                "departamento": "rh",
                "staff_token": "",
            },
        )
        user.refresh_from_db()

        self.assertRedirects(response, reverse("perfil"))
        self.assertEqual(user.email, "usuario.novo@gmail.com")
        self.assertEqual(user.first_name, "Usuário Novo")
        self.assertEqual(user.perfil.departamento, "rh")

    def test_perfil_com_token_promove_usuario(self):
        admin = self.criar_usuario(username="admin", is_staff=True)
        user = self.criar_usuario(username="usuario", is_staff=False)
        _, codigo = StaffToken.criar(admin)
        self.client.force_login(user)

        response = self.client.post(
            reverse("perfil"),
            {
                "email": user.email,
                "first_name": user.first_name,
                "departamento": user.perfil.departamento,
                "staff_token": codigo,
            },
        )
        user.refresh_from_db()

        self.assertRedirects(response, reverse("perfil"))
        self.assertTrue(user.is_staff)

    def test_perfil_invalido_nao_atualiza(self):
        user = self.criar_usuario(username="usuario", email="usuario@gmail.com")
        self.client.force_login(user)

        response = self.client.post(
            reverse("perfil"),
            {
                "email": "usuario@example.com",
                "first_name": "Usuário",
                "departamento": "ti",
                "staff_token": "",
            },
        )
        user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.email, "usuario@gmail.com")
        self.assertIn("email", response.context["form"].errors)


@override_settings(ROOT_URLCONF="core.urls", PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class AdministracaoViewTests(BaseCoreTestCase):
    def setUp(self):
        self.admin = self.criar_usuario(username="admin", is_staff=True, is_superuser=True, first_name="Admin")
        self.staff = self.criar_usuario(username="staff", is_staff=True, first_name="Moderador")
        self.comum = self.criar_usuario(username="comum", is_staff=False, first_name="Comum")

    def test_apenas_superuser_acessa_administracao(self):
        self.client.force_login(self.comum)
        negado = self.client.get(reverse("administracao"))
        self.assertRedirects(negado, reverse("listagem"))

        self.client.force_login(self.admin)
        permitido = self.client.get(reverse("administracao"))
        self.assertEqual(permitido.status_code, 200)
        self.assertIn("tokens", permitido.context)
        self.assertIn("forms_usuarios", permitido.context)

    def test_admin_cria_token_de_moderador(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("administracao"), {"acao": "criar_token", "descricao": "Convite de moderador"})
        token = StaffToken.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(token.criado_por, self.admin)
        self.assertEqual(token.descricao, "Convite de moderador")
        self.assertTrue(response.context["novo_codigo"])

    def test_admin_revoga_token_ativo(self):
        token, _ = StaffToken.criar(self.admin, descricao="Token para revogar")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("administracao"), {"acao": "revogar_token", "token_id": token.pk})
        token.refresh_from_db()

        self.assertRedirects(response, reverse("administracao"))
        self.assertFalse(token.ativo)

    def test_admin_nao_revoga_token_usado(self):
        token, _ = StaffToken.criar(self.admin, descricao="Token usado")
        token.ativo = False
        token.usado_por = self.staff
        token.usado_em = timezone.now()
        token.save(update_fields=["ativo", "usado_por", "usado_em"])
        self.client.force_login(self.admin)

        response = self.client.post(reverse("administracao"), {"acao": "revogar_token", "token_id": token.pk})
        token.refresh_from_db()

        self.assertRedirects(response, reverse("administracao"))
        self.assertFalse(token.ativo)
        self.assertIn("Este token já foi utilizado.", self.mensagens(response))

    def test_admin_edita_nome_e_departamento_de_usuario(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("administracao"),
            {
                "acao": "editar_usuario",
                "usuario": self.comum.pk,
                "first_name": "Comum Atualizado",
                "departamento": "ma",
            },
        )
        self.comum.refresh_from_db()

        self.assertRedirects(response, reverse("administracao"))
        self.assertEqual(self.comum.first_name, "Comum Atualizado")
        self.assertEqual(self.comum.perfil.departamento, "ma")

    def test_admin_alterna_usuario_ativo_mas_nao_desativa_superuser(self):
        self.client.force_login(self.admin)

        desativar = self.client.post(reverse("administracao"), {"acao": "alternar_ativo_usuario", "usuario": self.comum.pk})
        self.comum.refresh_from_db()
        self.assertRedirects(desativar, reverse("administracao"))
        self.assertFalse(self.comum.is_active)

        impedir = self.client.post(reverse("administracao"), {"acao": "alternar_ativo_usuario", "usuario": self.admin.pk})
        self.admin.refresh_from_db()
        self.assertRedirects(impedir, reverse("administracao"))
        self.assertTrue(self.admin.is_active)
        self.assertIn("Não é possível desativar um administrador.", self.mensagens(impedir))

    def test_admin_remove_permissao_de_moderador(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("administracao"), {"acao": "desmoderar_usuario", "usuario": self.staff.pk})
        self.staff.refresh_from_db()

        self.assertRedirects(response, reverse("administracao"))
        self.assertFalse(self.staff.is_staff)

    def test_admin_nao_desmodera_superuser_ou_usuario_comum(self):
        self.client.force_login(self.admin)

        superuser = self.client.post(reverse("administracao"), {"acao": "desmoderar_usuario", "usuario": self.admin.pk})
        comum = self.client.post(reverse("administracao"), {"acao": "desmoderar_usuario", "usuario": self.comum.pk})
        self.admin.refresh_from_db()
        self.comum.refresh_from_db()

        self.assertTrue(self.admin.is_staff)
        self.assertFalse(self.comum.is_staff)
        self.assertIn("Não é possível desmoderar um administrador.", self.mensagens(superuser))
        self.assertIn("Este usuário não é moderador.", self.mensagens(comum))


@override_settings(PASSWORD_HASHERS=FAST_PASSWORD_HASHERS)
class DemonstracaoCommandTests(TestCase):
    def test_comando_demonstracao_cria_usuarios_perfis_perguntas_respostas_e_tokens(self):
        out = StringIO()

        call_command("demonstracao", stdout=out)

        self.assertIn("Demonstração criada com sucesso.", out.getvalue())
        self.assertEqual(User.objects.count(), 9)
        self.assertEqual(Perfil.objects.count(), 9)
        self.assertEqual(Pergunta.objects.count(), 20)
        self.assertGreaterEqual(Resposta.objects.count(), 20)
        self.assertEqual(StaffToken.objects.count(), 2)

        arthur = User.objects.get(username="arthur")
        anabelle = User.objects.get(username="anabelle")
        self.assertTrue(arthur.is_superuser)
        self.assertTrue(arthur.is_staff)
        self.assertTrue(arthur.check_password("teste1234"))
        self.assertEqual(arthur.perfil.departamento, "ti")
        self.assertTrue(anabelle.is_staff)
        self.assertEqual(anabelle.perfil.departamento, "rh")

        reabertas = Pergunta.objects.exclude(motivo_reabertura="")
        self.assertEqual(reabertas.count(), 2)
        self.assertEqual(reabertas.filter(reaberta_por__isnull=False, reaberta_em__isnull=False).count(), 2)
        self.assertEqual(StaffToken.objects.filter(ativo=False).count(), 2)
        self.assertEqual(StaffToken.objects.filter(usado_em__isnull=False, usado_por=anabelle).count(), 1)
