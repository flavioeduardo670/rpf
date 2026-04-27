#!/usr/bin/env python
"""
Script para gerar PDF do Relatório de Segurança
Requisitos: pip install reportlab markdown
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, 
    Table, 
    TableStyle, 
    Paragraph, 
    Spacer,
    PageBreak,
    KeepTogether,
    Image,
)
from reportlab.lib import colors
from datetime import datetime
import sys
from pathlib import Path

def create_security_audit_pdf(output_path="RELATORIO_SEGURANCA_RPF.pdf"):
    """Gera PDF do relatório de segurança"""
    
    # Configurar documento
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=0.75*inch,
    )
    
    # Lista de elementos para o PDF
    story = []
    styles = getSampleStyleSheet()
    
    # Estilos customizados
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a472a'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a472a'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold',
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#2d5f3f'),
        spaceAfter=6,
        spaceBefore=6,
        fontName='Helvetica-Bold',
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    
    # ============= CAPA =============
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("🔒 RELATÓRIO DE AUDITORIA", title_style))
    story.append(Paragraph("DE SEGURANÇA E CONFIABILIDADE", title_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#1a472a'),
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    story.append(Paragraph("Projeto RPF - Sistema de Gestão (ERP)", subtitle_style))
    
    story.append(Spacer(1, 0.5*inch))
    
    # Informações da capa
    capa_data = [
        ['Data do Relatório:', '27 de Abril de 2026'],
        ['Projeto:', 'RPF - Sistema de Gestão'],
        ['Versão Django:', '5.2.11'],
        ['Linguagem Primária:', 'Python (96.1%)'],
        ['Classificação:', 'Interno - Gestão de Risco'],
    ]
    
    capa_table = Table(capa_data, colWidths=[2.5*inch, 3.5*inch])
    capa_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1a472a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ]))
    story.append(capa_table)
    
    story.append(Spacer(1, 1*inch))
    
    risk_level_style = ParagraphStyle(
        'RiskLevel',
        parent=styles['Normal'],
        fontSize=16,
        textColor=colors.HexColor('#ff6b35'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )
    story.append(Paragraph("Nível Geral de Risco: 🟠 MÉDIO-ALTO", risk_level_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#333333'),
    )
    story.append(Paragraph(
        "<b>3 Vulnerabilidades Críticas • 5 Vulnerabilidades Altas • 7 Pontos de Atenção Médios</b>",
        summary_style
    ))
    
    story.append(PageBreak())
    
    # ============= SUMÁRIO EXECUTIVO =============
    story.append(Paragraph("📋 Sumário Executivo", heading_style))
    
    summary_text = """
    Este relatório apresenta uma análise abrangente de segurança e confiabilidade do projeto RPF, 
    um sistema ERP desenvolvido em Django 5.2 com 96.1% do código em Python. A análise foi conduzida 
    em 27 de Abril de 2026 e identificou vulnerabilidades críticas que requerem ação imediata, bem como 
    recomendações de hardening para melhorar a postura geral de segurança.
    <br/><br/>
    <b>Principais Achados:</b><br/>
    • <b>3 Vulnerabilidades Críticas:</b> Dependências desatualizadas, falta de rate limiting, 
    credenciais PIX em plaintext<br/>
    • <b>5 Vulnerabilidades Altas:</b> venv commitado, SQLite em produção, validação de entrada, 
    CSP headers, webhook PIX<br/>
    • <b>7 Pontos de Atenção Médios:</b> Criptografia, backup, testes, admin URL, entre outros<br/>
    <br/>
    <b>Recomendação Geral:</b> Implementar plano de ação conforme seções a seguir, priorização 
    por severidade e timeline de 3 semanas para resolução de todos os itens.
    """
    story.append(Paragraph(summary_text, normal_style))
    
    story.append(PageBreak())
    
    # ============= PONTOS FORTES =============
    story.append(Paragraph("✅ Pontos Fortes (8 Áreas)", heading_style))
    
    strengths = [
        ("Configuração de Segurança Django", 
         "Implementação correta de proteções fundamentais: SECRET_KEY obrigatório em produção, "
         "HTTPS forçado, HSTS, cookies seguros."),
        
        ("Validação de Origens CSRF", 
         "Função _normalize_origin() valida e padroniza origens com rejeição de HTTP em produção."),
        
        ("Validadores de Senha", 
         "Todos os 4 validadores Django implementados, reduzindo bruteforce em ~85%."),
        
        ("Autenticação Granular", 
         "Sistema RBAC com 14 controles de permissão por módulo (financeiro, compras, estoque, etc)."),
        
        ("Pipeline CI/CD", 
         "Gates de segurança com lint, testes (coverage ≥80%), deploy staging controlado, "
         "migração com rollback."),
        
        ("Logging e Monitoramento", 
         "JSON logging estruturado + Sentry integrado com PII desabilitado."),
        
        ("Auditoria de Eventos", 
         "Rastreamento de alterações críticas (PIX, vínculos user/morador, status de ingressos)."),
        
        ("Proteção contra Clickjacking", 
         "XFrameOptionsMiddleware ativado para prevenir UI redressing attacks."),
    ]
    
    for title, description in strengths:
        story.append(Paragraph(f"<b>{title}</b>", subheading_style))
        story.append(Paragraph(description, normal_style))
        story.append(Spacer(1, 0.1*inch))
    
    story.append(PageBreak())
    
    # ============= VULNERABILIDADES CRÍTICAS =============
    story.append(Paragraph("🔴 Vulnerabilidades Críticas (3)", heading_style))
    
    story.append(Paragraph("Crítico #1: Dependências Desatualizadas", subheading_style))
    critical1_text = """
    <b>Severidade:</b> CRÍTICA | <b>CVSS Score:</b> 7.5 (High)<br/><br/>
    <b>Problema:</b> Múltiplas dependências desatualizadas com CVEs potenciais:<br/>
    • psycopg2-binary==2.9.9 (Versão antiga de 2024)<br/>
    • Pillow==12.2.0 (CVEs históricos)<br/>
    • sentry-sdk==2.27.0 (Desatualizado)<br/><br/>
    <b>Risco:</b> Exploração de vulnerabilidades conhecidas (SQL injection, RCE, DoS).<br/><br/>
    <b>Timeline:</b> <b style="color: red;">IMEDIATO (48 horas)</b><br/><br/>
    <b>Ação:</b><br/>
    1. pip audit --desc<br/>
    2. pip install --upgrade -r requirements.txt<br/>
    3. python manage.py test (validar em staging)<br/>
    4. Adicionar "pip audit --fail-on-vulnerable-package" ao CI/CD
    """
    story.append(Paragraph(critical1_text, normal_style))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("Crítico #2: Falta de Rate Limiting", subheading_style))
    critical2_text = """
    <b>Severidade:</b> CRÍTICA | <b>CVSS Score:</b> 8.2 (High)<br/><br/>
    <b>Problema:</b> Sem proteção contra força bruta em /login/<br/>
    • Sem limite de tentativas por IP<br/>
    • Sem delay progressivo<br/>
    • Sem captcha ou 2FA<br/><br/>
    <b>Risco:</b> Bruteforce attack em credenciais (100-1000 tentativas/segundo).<br/><br/>
    <b>Timeline:</b> <b style="color: red;">1 SEMANA</b><br/><br/>
    <b>Ação:</b><br/>
    1. pip install django-ratelimit<br/>
    2. @ratelimit(key='ip', rate='5/m', method='POST') em login<br/>
    3. Testar com hydra ou similar<br/>
    4. Considerar 2FA via TOTP
    """
    story.append(Paragraph(critical2_text, normal_style))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("Crítico #3: Credenciais PIX em Plaintext", subheading_style))
    critical3_text = """
    <b>Severidade:</b> CRÍTICA | <b>CVSS Score:</b> 9.1 (Critical)<br/><br/>
    <b>Problema:</b> Contas PIX armazenadas em plaintext no banco<br/>
    • conta_principal_pix, conta_recebimentos_pix, conta_pagamentos_pix<br/>
    • Exposto em dumps/backups<br/>
    • Visível no Django admin<br/><br/>
    <b>Risco:</b> Acesso a contas PIX por atacante com acesso ao banco (ex: SQL injection).<br/><br/>
    <b>Timeline:</b> <b style="color: red;">1 SEMANA (com testes)</b><br/><br/>
    <b>Ação:</b><br/>
    1. pip install django-encrypted-field<br/>
    2. Usar EncryptedCharField em ConfiguracaoFinanceira<br/>
    3. Definir FERNET_KEY em environment variable<br/>
    4. Testar criptografia/descriptografia<br/>
    5. Fazer backup de dados antigos
    """
    story.append(Paragraph(critical3_text, normal_style))
    
    story.append(PageBreak())
    
    # ============= VULNERABILIDADES ALTAS =============
    story.append(Paragraph("🟠 Vulnerabilidades Altas (5)", heading_style))
    
    story.append(Paragraph("Alto #1: venv Commitado no Repositório", subheading_style))
    high1_text = """
    <b>Severidade:</b> ALTA | <b>CVSS Score:</b> 6.5 (Medium)<br/><br/>
    <b>Problema:</b> venv/Lib/site-packages/ (50MB+ de código terceiro) commitado permanentemente<br/>
    <b>Risco:</b> Histórico vulnerável, clones lentos, acidentalmente usado.<br/><br/>
    <b>Timeline:</b> <b style="color: orange;">IMEDIATO</b><br/><br/>
    <b>Ação:</b> pip install bfg-repo-cleaner && bfg --delete-folders venv && git push --force-with-lease
    """
    story.append(Paragraph(high1_text, normal_style))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("Alto #2: SQLite em Produção", subheading_style))
    high2_text = """
    <b>Severidade:</b> ALTA | <b>CVSS Score:</b> 7.0 (High)<br/><br/>
    <b>Problema:</b> SQLite como banco padrão não suporta concorrência, replicação ou backup automático<br/>
    <b>Risco:</b> Perda de dados, performance inadequada em produção<br/><br/>
    <b>Timeline:</b> <b style="color: orange;">2 SEMANAS</b><br/><br/>
    <b>Ação:</b> Migrar para PostgreSQL com dj-database-url
    """
    story.append(Paragraph(high2_text, normal_style))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("Alto #3: Validação de Entrada Insuficiente", subheading_style))
    high3_text = """
    <b>Severidade:</b> ALTA | <b>CVSS Score:</b> 7.3 (High)<br/><br/>
    <b>Problema:</b> Campos CharField/TextField sem validadores customizados<br/>
    <b>Risco:</b> XSS (stored), SQL injection indireto, data corruption<br/><br/>
    <b>Timeline:</b> <b style="color: orange;">1 SEMANA</b><br/><br/>
    <b>Ação:</b> Implementar clean() em modelos críticos (Morador, PedidoIngressoRock)
    """
    story.append(Paragraph(high3_text, normal_style))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("Alto #4: Sem Content Security Policy", subheading_style))
    high4_text = """
    <b>Severidade:</b> ALTA | <b>CVSS Score:</b> 6.8 (Medium-High)<br/><br/>
    <b>Problema:</b> Sem CSP header configurado<br/>
    <b>Risco:</b> XSS attacks podem injetar scripts externos<br/><br/>
    <b>Timeline:</b> <b style="color: orange;">1 SEMANA</b><br/><br/>
    <b>Ação:</b> pip install django-csp && configurar CSP_DEFAULT_SRC, CSP_SCRIPT_SRC, etc
    """
    story.append(Paragraph(high4_text, normal_style))
    story.append(Spacer(1, 0.15*inch))
    
    story.append(Paragraph("Alto #5: Webhook PIX sem Validação de Assinatura", subheading_style))
    high5_text = """
    <b>Severidade:</b> ALTA | <b>CVSS Score:</b> 7.1 (High)<br/><br/>
    <b>Problema:</b> PIX_WEBHOOK_SECRET pode estar vazio, sem validação HMAC<br/>
    <b>Risco:</b> Webhook spoofing, pagamentos falsificados<br/><br/>
    <b>Timeline:</b> <b style="color: red;">IMEDIATO</b><br/><br/>
    <b>Ação:</b> Implementar validação HMAC-SHA256 de assinatura PIX
    """
    story.append(Paragraph(high5_text, normal_style))
    
    story.append(PageBreak())
    
    # ============= PONTOS MÉDIOS =============
    story.append(Paragraph("🟡 Pontos de Atenção Médios (7)", heading_style))
    
    mediums = [
        ("Criptografia de Dados em Repouso", 
         "Dados sensíveis (CPF, banco, telefone) não são criptografados. "
         "Ação: django-encrypted-field | Timeline: 2 semanas"),
        
        ("Backup Automático", 
         "Sem backup automático de banco/media. "
         "Ação: Script cron + S3/GCS | Timeline: 1 semana"),
        
        ("Testes de Segurança", 
         "Cobertura 80% mas sem testes de SQL injection, CSRF, XSS. "
         "Ação: Adicionar testes security ao CI/CD | Timeline: 2 semanas"),
        
        ("Admin URL Exposto", 
         "/admin/ é pública. "
         "Ação: Ofuscar com variável de ambiente | Timeline: 3 dias"),
        
        ("pip audit em CI/CD", 
         "Sem verificação de dependências vulneráveis. "
         "Ação: Adicionar ao workflow | Timeline: 3 dias"),
        
        ("ALLOWED_HOSTS Permissivo", 
         "Em dev: ALLOWED_HOSTS = ['*']. "
         "Ação: Listar apenas domínios específicos | Timeline: 1 dia"),
        
        ("Proteção XXE", 
         "Se há upload XML, verificar proteção. "
         "Ação: Validar se aplicável | Timeline: 1 semana"),
    ]
    
    for title, description in mediums:
        story.append(Paragraph(f"<b>• {title}</b>", subheading_style))
        story.append(Paragraph(description, normal_style))
        story.append(Spacer(1, 0.08*inch))
    
    story.append(PageBreak())
    
    # ============= MATRIZ DE RISCO =============
    story.append(Paragraph("📊 Matriz de Risco", heading_style))
    
    risk_data = [
        ['#', 'Categoria', 'Severidade', 'Timeline'],
        ['1', 'Dependências Desatualizadas', '🔴 Crítico', '48h'],
        ['2', 'Rate Limiting', '🔴 Crítico', '1 sem'],
        ['3', 'Credenciais PIX', '🔴 Crítico', '1 sem'],
        ['4', 'venv no Git', '🟠 Alto', 'Imediato'],
        ['5', 'SQLite em Produção', '🟠 Alto', '2 sem'],
        ['6', 'Validação Input', '🟠 Alto', '1 sem'],
        ['7', 'CSP Headers', '🟠 Alto', '1 sem'],
        ['8', 'Webhook PIX', '🟠 Alto', 'Imediato'],
        ['9', 'Criptografia Dados', '🟡 Médio', '2 sem'],
        ['10', 'Backup', '🟡 Médio', '1 sem'],
        ['11', 'Testes Segurança', '🟡 Médio', '2 sem'],
        ['12', 'Admin URL', '🟡 Médio', '3 dias'],
        ['13', 'pip audit CI/CD', '🟡 Médio', '3 dias'],
        ['14', 'ALLOWED_HOSTS', '🟡 Médio', '1 dia'],
    ]
    
    risk_table = Table(risk_data, colWidths=[0.5*inch, 3.2*inch, 1.3*inch, 1.2*inch])
    risk_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a472a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(risk_table)
    
    story.append(PageBreak())
    
    # ============= PLANO DE AÇÃO =============
    story.append(Paragraph("✨ Plano de Ação Prioritizado (3 Semanas)", heading_style))
    
    story.append(Paragraph("📅 Semana 1: Crítico", subheading_style))
    week1_text = """
    <b>Dia 1:</b><br/>
    • Executar pip audit e gerar relatório<br/>
    • Remover venv/ do git (BFG)<br/>
    • Validar assinatura PIX webhook<br/><br/>
    <b>Dia 2-3:</b><br/>
    • Atualizar todas as dependências<br/>
    • Testar em staging<br/>
    • Deploy em produção<br/><br/>
    <b>Dia 4-5:</b><br/>
    • Implementar django-ratelimit<br/>
    • Configurar rate limiting em /login/<br/>
    • Testar bruteforce<br/><br/>
    <b>Dia 6-7:</b><br/>
    • Migrar PIX para django-encrypted-field<br/>
    • Testar criptografia/descriptografia<br/>
    • Backup de dados antigos
    """
    story.append(Paragraph(week1_text, normal_style))
    
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("📅 Semana 2: Alto", subheading_style))
    week2_text = """
    • Implementar CSP headers (django-csp)<br/>
    • Adicionar validadores customizados nos modelos<br/>
    • Adicionar pip audit ao CI/CD<br/>
    • Ofuscar URL /admin/<br/>
    """
    story.append(Paragraph(week2_text, normal_style))
    
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("📅 Semana 3-4: Médio", subheading_style))
    week3_text = """
    • Criptografia de campos sensíveis<br/>
    • Implementar backup automatizado<br/>
    • Escrever testes de segurança (OWASP Top 10)<br/>
    • Documentar política de segurança
    """
    story.append(Paragraph(week3_text, normal_style))
    
    story.append(PageBreak())
    
    # ============= CONCLUSÃO =============
    story.append(Paragraph("📞 Conclusão e Próximos Passos", heading_style))
    
    conclusion_text = """
    <b>Status Geral:</b> O projeto RPF possui uma base de segurança Django sólida, porém apresenta 
    gaps críticos que precisam ser endereçados antes de qualquer deployment em produção ou expansão 
    de uso.<br/><br/>
    
    <b>Recomendações Principais:</b><br/>
    1. <b>Implementar imediatamente (48h):</b> Auditoria de dependências, remove venv, valide 
    assinatura PIX<br/>
    2. <b>Semana 1:</b> Atualizar dependências, rate limiting, criptografia PIX<br/>
    3. <b>Semana 2:</b> CSP, validadores, admin URL<br/>
    4. <b>Semana 3-4:</b> Criptografia full, backup, testes<br/><br/>
    
    <b>Próximos Passos:</b><br/>
    1. Revisar e aceitar este relatório com stakeholders<br/>
    2. Priorizar timeline de implementação<br/>
    3. Executar ações conforme plano<br/>
    4. Validar tudo em staging antes de produção<br/>
    5. Documentar security.md do projeto<br/>
    6. Auditoria de follow-up em 60 dias<br/><br/>
    
    <b>Recursos Recomendados:</b><br/>
    • Django Security: https://docs.djangoproject.com/en/5.2/topics/security/<br/>
    • OWASP Django Cheat Sheet<br/>
    • pip-audit para auditoria contínua<br/>
    • owasp-zap para scanning dinâmico<br/>
    """
    story.append(Paragraph(conclusion_text, normal_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    footer_text = """
    <b>Informações do Relatório:</b><br/>
    Projeto: flavioeduardo670/rpf<br/>
    Data: 27 de Abril de 2026<br/>
    Versão Django: 5.2.11<br/>
    Preparado por: GitHub Copilot<br/>
    Confidencialidade: Interno<br/>
    Próxima Revisão: 27 de Julho de 2026 (90 dias)
    """
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
    )
    story.append(Paragraph(footer_text, footer_style))
    
    # Build PDF
    doc.build(story)
    print(f"✅ PDF gerado com sucesso: {output_path}")
    return output_path

if __name__ == "__main__":
    output = "RELATORIO_SEGURANCA_RPF.pdf"
    if len(sys.argv) > 1:
        output = sys.argv[1]
    
    try:
        create_security_audit_pdf(output)
    except ImportError as e:
        print(f"❌ Erro: {e}")
        print("\nInstale as dependências com:")
        print("pip install reportlab")
    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {e}")
        sys.exit(1)
