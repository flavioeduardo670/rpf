from datetime import time

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import AtaLinha5W2H, AtaParticipante, AtaReuniao, AtaTopico, Morador, Reuniao


class AtaReuniaoRegistroTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='secretario', password='123456')
        self.reuniao = Reuniao.objects.create(
            tipo='setorial',
            setor='infraestrutura',
            data='2026-04-10',
            horario_marcado='20:00',
            local='Sala principal',
            status='realizada',
        )
        self.ata = AtaReuniao.objects.create(
            reuniao=self.reuniao,
            horario_inicio_real=time(20, 5),
            horario_fim_real=time(21, 0),
            criado_por=self.user,
        )

    def test_registrar_ata_gera_os_pdf_e_auditoria(self):
        AtaParticipante.objects.create(ata=self.ata, nome='Alice', presente=True)
        AtaTopico.objects.create(ata=self.ata, ordem=1, texto='Revisão de pendências')
        linha = AtaLinha5W2H.objects.create(
            ata=self.ata,
            o_que='Consertar porta da lavanderia',
            por_que='Segurança',
            onde='Lavanderia',
            quem='Alice',
            como='Trocar dobradiça e alinhamento',
            quanto='R$ 50',
        )

        total_os = self.ata.registrar(registrado_por=self.user)
        self.ata.refresh_from_db()
        linha.refresh_from_db()

        self.assertEqual(total_os, 1)
        self.assertEqual(self.ata.status, 'registrada')
        self.assertTrue(self.ata.gerou_os)
        self.assertEqual(self.ata.registrada_por, self.user)
        self.assertIsNotNone(self.ata.registrada_em)
        self.assertTrue(bool(self.ata.pdf_final.name))
        self.assertIsNotNone(linha.ordem_servico)

    def test_registro_sem_campos_obrigatorios_dispara_erro(self):
        self.ata.horario_inicio_real = None
        self.ata.save(update_fields=['horario_inicio_real'])
        with self.assertRaises(ValidationError):
            self.ata.registrar(registrado_por=self.user)

    def test_bloqueia_edicao_apos_registro(self):
        AtaParticipante.objects.create(ata=self.ata, nome='Alice', presente=True)
        AtaTopico.objects.create(ata=self.ata, ordem=1, texto='Pendências')
        self.ata.registrar(registrado_por=self.user)

        participante = self.ata.participantes.first()
        participante.nome = 'Alice 2'
        with self.assertRaises(ValidationError):
            participante.save()

    def test_idempotencia_de_geracao_os(self):
        AtaParticipante.objects.create(ata=self.ata, nome='Alice', presente=True)
        AtaTopico.objects.create(ata=self.ata, ordem=1, texto='Pendências')
        AtaLinha5W2H.objects.create(
            ata=self.ata,
            o_que='Trocar lâmpada',
            por_que='Iluminação',
            onde='Corredor',
            quem='Alice',
            como='Substituição simples',
        )

        primeira = self.ata.registrar(registrado_por=self.user)
        segunda = self.ata.registrar(registrado_por=self.user)

        self.assertEqual(primeira, 1)
        self.assertEqual(segunda, 0)
        self.assertEqual(self.ata.linhas_5w2h.exclude(ordem_servico__isnull=True).count(), 1)

    def test_participante_preenche_nome_a_partir_do_morador(self):
        morador = Morador.objects.create(nome='Bruno')
        participante = AtaParticipante.objects.create(ata=self.ata, morador=morador)
        self.assertEqual(participante.nome, 'Bruno')
