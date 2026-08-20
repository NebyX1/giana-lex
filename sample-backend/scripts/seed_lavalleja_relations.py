"""Register known initial normative relationships for Lavalleja digesto."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from depto import storage as st

RELATIONS = [
    # Estatuto del funcionario: 3842/023 modifica 994/982 (Estatuto)
    {"from": "decreto:3842:2023", "relation": "MODIFIES", "to": "decreto:994:1982", "status": "verified", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3842-fecha-25092023"},
    # 3982/025 también modifica 994/982
    {"from": "decreto:3982:2025", "relation": "MODIFIES", "to": "decreto:994:1982", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3982-fecha-11062025"},
    # Procedimiento administrativo: 1145/993 incorpora Decreto Nacional 500/991
    {"from": "decreto:1145:1993", "relation": "INCORPORATES", "to": "decreto:500:1991", "status": "verified", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-3698024"},
    # Decreto Nacional 420/007 modifica 500/991 (corpus nacional)
    {"from": "decreto:420:2007", "relation": "MODIFIES", "to": "decreto:500:1991", "status": "verified", "evidence_source": "https://www.impo.com.uy/bases/decretos/420-2007"},
    # 3673/021 incorpora Decreto Nacional 276/013 (presupuesto)
    {"from": "decreto:3673:2021", "relation": "INCORPORATES", "to": "decreto:276:2013", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3673-fecha-16082021"},
    # 524/977 hace aplicable Código Tributario Nacional (codigo-tributario:14306:1974)
    {"from": "decreto:524:1977", "relation": "INCORPORATES", "to": "codigo-tributario:14306:1974", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3945-fecha-19022025"},
    # Cementerios: 3366/016 modifica art 29 de 761/1990
    {"from": "decreto:3366:2016", "relation": "MODIFIES_ARTICLE", "to": "decreto:761:1990", "target_article": "29", "status": "verified", "evidence_source": "https://new.jdl.uy/wp-content/uploads/2025/10/3366_Modificacion_Art_29_del_Decreto_761_1990_literal_H_sobre_arrendamiento_nichos.pdf"},
    # 903/81 modifica régimen histórico de cementerios (1944)
    {"from": "decreto:903:1981", "relation": "MODIFIES", "to": "ordenanza:cementerios:1944", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-1475025"},
    # Ordenamiento territorial: 3571/019 regula/desarrolla Ordenanza 2004
    {"from": "decreto:3571:2019", "relation": "REGULATES", "to": "ordenanza:desarrollo-ordenamiento-territorial:2004", "status": "candidate", "evidence_source": "https://www.lavalleja.gub.uy/c/document_library/get_file?folderId=1462710&name=DLFE-11204.pdf"},
    # 3854/023 modifica 3571/019
    {"from": "decreto:3854:2023", "relation": "MODIFIES", "to": "decreto:3571:2019", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3854-fecha-01112023"},
    # 3907/024 y 3934/024 continúan cadena territorial
    {"from": "decreto:3907:2024", "relation": "MODIFIES", "to": "decreto:3854:2023", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3907-fecha-14082024"},
    {"from": "decreto:3934:2024", "relation": "MODIFIES", "to": "decreto:3854:2023", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3934-fecha-13112024"},
    # 3941/024 relación patrimonio con 3326/015
    {"from": "decreto:3941:2024", "relation": "RELATED_TO", "to": "decreto:3326:2015", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3941-fecha-11122024"},
    # Fideicomiso: 3951/025 relacionado con 3473
    {"from": "decreto:3951:2025", "relation": "RELATED_TO", "to": "decreto:3473:unknown", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3951-fecha-19022025"},
    # Zona azul genealogía
    {"from": "decreto:3760:2022", "relation": "MODIFIES", "to": "decreto:3087:2012", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3760-fecha-09112022"},
    {"from": "decreto:3087:2012", "relation": "MODIFIES", "to": "decreto:2995:2011", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3760-fecha-09112022"},
    {"from": "decreto:2995:2011", "relation": "MODIFIES", "to": "decreto:1456:1995", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3760-fecha-09112022"},
    # Pirotecnia: 3767/022 modifica 3640/020
    {"from": "decreto:3767:2022", "relation": "MODIFIES", "to": "decreto:3640:2020", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3767-fecha-23112022"},
    # Municipios: 3368/016 reglamenta Ley 19272
    {"from": "decreto:3368:2016", "relation": "REGULATES", "to": "ley:19272:2014", "status": "candidate", "evidence_source": "https://juntadepartamentallavalleja.gub.uy/ova_doc/3368_reglamento_municipios_del_dpto/"},
    # Edificación: 3786/023 modifica 1064/983
    {"from": "decreto:3786:2023", "relation": "MODIFIES", "to": "decreto:1064:1983", "status": "candidate", "evidence_source": "https://www.gub.uy/intendencia-lavalleja/institucional/normativa/decreto-departamental-n-3786-fecha-08032023"},
    # 3468/017 interpreta art 17 de 3442/017
    {"from": "decreto:3468:2017", "relation": "INTERPRETS_ARTICLE", "to": "decreto:3442:2017", "target_article": "17", "status": "verified", "evidence_source": "https://juntadepartamentallavalleja.gub.uy/ova_doc/3468_decreto_interpretativo_art_17_decreto_3442/"},
]

added = 0
for rel in RELATIONS:
    if st.add_relationship(rel):
        added += 1
print(f"Added {added} initial relationships. Total: {st.count_relationships()}")