"""
Pruebas del traductor que no necesitan modelos ni GPU: capa léxica, patrones, reordenamiento n-best,
conversión de confianza y separación estable de entrenamiento/evaluación.

  python manage.py test traduccion
"""
from django.test import TestCase

from terminos.models import Lengua, TerminoEs, TerminoLeng

from . import lexico, reranking
from .pipeline import confianza_semantica, nivel_semantico


def _t(lengua, termino, es, pos='NOM', sin=None, tipo=None):
    es_obj, _ = TerminoEs.objects.get_or_create(termino=es)
    return TerminoLeng.objects.create(lengua=lengua, termino=termino, termino_es=es_obj, definicion=f'{es}.', pos=pos, sinonimos=sin or [], tipo_morfema=tipo)


class NormalizacionTests(TestCase):
    def test_normalizar_unifica_grafias(self):
        self.assertEqual(lexico.normalizar('Kʉkʉ'), lexico.normalizar('KUKU'))
        self.assertEqual(lexico.normalizar("Sakʉn na'mʉchʉyin,"), 'sakun namuchuyin')
        self.assertEqual(lexico.normalizar('Ɉwa'), 'jwa')
        self.assertEqual(lexico.normalizar('¿Mañ-mañ zalda?'), 'man man zalda')  # ñ→n: «mañ» y «man» coinciden
        self.assertEqual(lexico.normalizar(''), '')


class LexicoTests(TestCase):
    def setUp(self):
        self.kg = Lengua.objects.create(codigo='Kogui', nombre='Kogui')
        self.ik = Lengua.objects.create(codigo='1', nombre='Ikʉn')
        _t(self.kg, 'Abbi', 'sangre')
        _t(self.kg, 'Abbi isha', 'deposición con sangre')
        _t(self.kg, 'Munzhi zhawa', 'hija')
        _t(self.kg, 'Guañ-gua zalda', 'fiebre')
        _t(self.kg, 'Mañ mañ', 'mareo')
        _t(self.kg, 'itshani', 'Tristeza', tipo='hipótesis')
        _t(self.ik, 'Biwkʉnʉ', 'rodilla')
        _t(self.ik, 'Kwi’', 'hombro')
        _t(self.ik, 'Du zari bunsi chano', 'buenos días')
        lexico.invalidar()

    def test_exacta_gana_siempre(self):
        r = lexico.buscar_lexico('Abbi', 'Kogui', 'lengua_a_es')
        self.assertEqual(r[0]['termino'], 'Abbi')
        self.assertEqual(r[0]['confianza'], 100)
        self.assertEqual(r[0]['nivel'], 'exacta')

    def test_aproximada_tolera_error_de_escritura(self):
        r = lexico.buscar_lexico('Munzhi zawa', 'Kogui', 'lengua_a_es')
        self.assertEqual(r[0]['termino'], 'Munzhi zhawa')
        self.assertEqual(r[0]['nivel'], 'aproximada')
        self.assertGreaterEqual(r[0]['confianza'], 80)

    def test_direccion_espanol(self):
        r = lexico.buscar_lexico('fiebre', 'Kogui', 'es_a_lengua')
        self.assertEqual(r[0]['termino'], 'Guañ-gua zalda')
        self.assertEqual(r[0]['confianza'], 100)

    def test_parcial_marca_termino_dentro_del_texto(self):
        r = lexico.buscar_lexico('Abbi isha mikzek', 'Kogui', 'lengua_a_es')
        self.assertEqual(r[0]['termino'], 'Abbi isha')
        self.assertEqual(r[0]['nivel'], 'parcial')

    def test_hipotesis_queda_marcada(self):
        r = lexico.buscar_lexico('itshani', 'Kogui', 'lengua_a_es')
        self.assertTrue(r[0]['hipotesis'])

    def test_patron_kogui_tiempos(self):
        r = lexico.buscar_patrones('¿Mañ-mañ zalda mikzegate nauke?', 'Kogui', 'lengua_a_es')
        self.assertTrue(r)
        self.assertIn('mareo', r[0]['termino_es'].lower())
        self.assertEqual(r[0]['fuente'], 'patrón')

    def test_patron_iku_dolor(self):
        r = lexico.buscar_patrones("Biwkʉna na'mʉchʉyin", '1', 'lengua_a_es')
        self.assertTrue(r)
        self.assertEqual(r[0]['termino_es'], 'me duele la rodilla')
        r2 = lexico.buscar_patrones("kwise' na'mʉchʉyin", '1', 'lengua_a_es')
        self.assertEqual(r2[0]['termino_es'], 'me duele en el hombro')

    def test_piezas_en_texto(self):
        p = lexico.piezas_en_texto('Munzhi zhawa guañ gua zalda', 'Kogui', 'lengua_a_es')
        self.assertEqual([x['equivalente'] for x in p], ['hija', 'fiebre'])

    def test_indice_se_invalida_al_guardar(self):
        self.assertFalse(lexico.buscar_lexico('zzznuevo', 'Kogui', 'lengua_a_es'))
        _t(self.kg, 'Zzznuevo', 'nuevo')
        lexico.invalidar('Kogui')
        self.assertEqual(lexico.buscar_lexico('zzznuevo', 'Kogui', 'lengua_a_es')[0]['confianza'], 100)

    def test_reordenamiento_nbest_prefiere_evidencia(self):
        i, det = reranking.elegir_transcripcion(['Abi ishaa mikzek', 'Abbi isha mikzek', 'Avi isa'], 'Kogui')
        self.assertEqual(i, 1)
        self.assertTrue(det[1]['elegida'])

    def test_reordenamiento_respeta_orden_en_empate(self):
        i, _ = reranking.elegir_transcripcion(['xxxx yyyy', 'zzzz wwww'], 'Kogui')
        self.assertEqual(i, 0)


class ConfianzaTests(TestCase):
    def test_conversion_monotona_y_acotada(self):
        self.assertEqual(confianza_semantica(0.50), 0)
        self.assertEqual(confianza_semantica(0.90), 100)
        self.assertLess(confianza_semantica(0.65), confianza_semantica(0.74))
        self.assertEqual(nivel_semantico(70), 'alta')
        self.assertEqual(nivel_semantico(50), 'media')
        self.assertEqual(nivel_semantico(10), 'baja')


class SplitEstableTests(TestCase):
    def test_split_por_audio_es_estable_y_sin_solape(self):
        from entrenamiento.services.training_service import dividir_train_eval
        samples = [{'audio': f'/x/Grabaciones/Kogui/jornada_a/audios_sin_procesar/a{i}.wav', 'sentence': 's'} for i in range(500)]
        tr, ev = dividir_train_eval(samples)
        tr2, ev2 = dividir_train_eval(list(reversed(samples)) + samples[:7])
        self.assertTrue(40 <= len(ev) <= 65)
        self.assertEqual({s['audio'] for s in ev}, {s['audio'] for s in ev2})
        self.assertFalse({s['audio'] for s in ev} & {s['audio'] for s in tr})

    def test_split_por_hablante_mantiene_voz_en_un_solo_lado(self):
        from entrenamiento.services.training_service import dividir_train_eval
        from translator_api.models import AudioMetadato
        samples = []
        for h in range(20):
            for i in range(10):
                nombre = f'h{h}_{i}.wav'
                samples.append({'audio': f'/x/Grabaciones/Kogui/jornada_b/audios_sin_procesar/{nombre}', 'sentence': 's'})
                AudioMetadato.objects.create(comunidad='Kogui', jornada='jornada_b', audio=nombre, hablante=f'Hablante {h}')
        tr, ev = dividir_train_eval(samples)
        lado = {}
        for s in tr:
            lado.setdefault(s['audio'].split('/')[-1].split('_')[0], set()).add('tr')
        for s in ev:
            lado.setdefault(s['audio'].split('/')[-1].split('_')[0], set()).add('ev')
        self.assertTrue(all(len(v) == 1 for v in lado.values()), lado)
