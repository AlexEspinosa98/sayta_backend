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

    def test_prefijo_solo_en_modo_sugerencias(self):
        self.assertFalse([r for r in lexico.buscar_lexico('munz', 'Kogui', 'lengua_a_es') if r['nivel'] == 'prefijo'])
        r = lexico.buscar_lexico('munz', 'Kogui', 'lengua_a_es', prefijos=True)
        self.assertEqual(r[0]['termino'], 'Munzhi zhawa')
        self.assertEqual(r[0]['nivel'], 'prefijo')
        r2 = lexico.buscar_lexico('fieb', 'Kogui', 'es_a_lengua', prefijos=True)
        self.assertEqual(r2[0]['termino_es'], 'fiebre')

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


class ComposicionTests(TestCase):
    """Frase armada con piezas del glosario y huecos marcados; huecos registrados como faltantes."""

    def setUp(self):
        self.kg = Lengua.objects.create(codigo='Kogui', nombre='Kogui')
        _t(self.kg, 'Natue', 'hermano')
        _t(self.kg, 'Ñi', 'agua')
        _t(self.kg, 'Guañ-gua zalda', 'fiebre')
        lexico.invalidar()

    def test_componer_marca_huecos_y_respeta_orden(self):
        from . import composicion
        texto = 'mi hermano come arepa'
        piezas = lexico.piezas_en_texto(texto, 'Kogui', 'es_a_lengua')
        c = composicion.componer(texto, 'es_a_lengua', piezas)
        self.assertEqual(c['frase'], '[mi] Natue [come] [arepa]')
        self.assertEqual(c['huecos'], ['come', 'arepa'])   # «mi» es funcional: no se pide a la comunidad
        self.assertFalse(c['completa'])
        self.assertEqual(c['piezas_audio'], ['Natue'])

    def test_funcionales_no_son_faltantes(self):
        from . import composicion
        texto = 'el agua y la fiebre'
        piezas = lexico.piezas_en_texto(texto, 'Kogui', 'es_a_lengua')
        c = composicion.componer(texto, 'es_a_lengua', piezas)
        self.assertEqual(c['frase'], '[el] Ñi [y] [la] Guañ-gua zalda')
        self.assertEqual(c['huecos'], [])            # el / y / la son funcionales: no se piden a la comunidad
        self.assertEqual(c['piezas_audio'], ['Ñi', 'Guañ-gua zalda'])

    def test_completa_cuando_todo_esta_en_glosario(self):
        from . import composicion
        texto = 'hermano agua'
        piezas = lexico.piezas_en_texto(texto, 'Kogui', 'es_a_lengua')
        c = composicion.componer(texto, 'es_a_lengua', piezas)
        self.assertTrue(c['completa'])
        self.assertEqual(c['frase'], 'Natue Ñi')

    def test_registrar_y_resolver_faltantes(self):
        from .models import TerminoFaltante
        from .views_aprendizaje import registrar_faltantes, resolver_faltantes
        ver = {'compuesta_honesta': {'huecos': ['come', 'arepa']}}
        registrar_faltantes(self.kg, 'es_a_lengua', 'mi hermano come arepa', ver)
        registrar_faltantes(self.kg, 'es_a_lengua', 'ella come', {'compuesta_honesta': {'huecos': ['Come']}})
        come = TerminoFaltante.objects.get(texto_normalizado='come')
        self.assertEqual(come.veces, 2)
        self.assertEqual(TerminoFaltante.objects.filter(estado='pendiente').count(), 2)
        _t(self.kg, 'Kawu', 'come')   # alguien lo agrega al glosario
        lexico.invalidar()
        self.assertEqual(resolver_faltantes('Kogui'), 1)
        come.refresh_from_db()
        self.assertEqual(come.estado, 'resuelto')
        self.assertEqual(come.termino.termino, 'Kawu')


class AudioFraseTests(TestCase):
    def test_elegir_clips_prefiere_misma_jornada(self):
        from unittest import mock
        from . import audio_frase
        ejemplos = {
            'natue': [{'comunidad': 'Kogui', 'jornada': 'j1', 'audio': 'a.wav'}, {'comunidad': 'Kogui', 'jornada': 'j2', 'audio': 'b.wav'}],
            'ni': [{'comunidad': 'Kogui', 'jornada': 'j2', 'audio': 'c.wav'}],
            'xyz': [],
        }
        with mock.patch.object(audio_frase.audio_ejemplo, 'ejemplos', side_effect=lambda p, c, n: [dict(e) for e in ejemplos[lexico.normalizar(p)]]), \
             mock.patch.object(audio_frase, '_hablante', return_value=''):
            elegidos, resumen = audio_frase.elegir_clips(['Natue', 'Ñi', 'xyz'], 'Kogui')
        self.assertEqual([e['audio'] if e else None for e in elegidos], ['b.wav', 'c.wav', None])
        self.assertEqual(resumen['con_audio'], 2)
        self.assertEqual(resumen['faltantes'], ['xyz'])
        self.assertEqual(resumen['jornadas'], ['j2'])


class GuardianComposicionTests(TestCase):
    def test_candidata_semantica_ajena_no_entra_en_la_composicion(self):
        from .agentes import _tokens_permitidos
        candidatos = [{'termino': 'Natue', 'termino_es': 'hermano'}, {'termino': 'niuwi neialda gue', 'termino_es': 'buenas tardes'}]
        piezas = [{'termino_lengua': 'Natue', 'termino_es': 'hermano', 'fragmento': 'hermano'}]
        permitidos = _tokens_permitidos('mi hermano come arepa', candidatos, piezas)
        self.assertIn('natue', permitidos)
        self.assertNotIn('niuwi', permitidos)


class SintesisVozGatingTests(TestCase):
    """Mientras la voz sintética entrena, solo los superusuarios la ven; el resto recibe «no disponible»."""

    def _get(self, user, **params):
        from unittest import mock
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views_aprendizaje import SintesisVozView
        req = APIRequestFactory().get('/api/traduccion/sintetizar/', params)
        force_authenticate(req, user=user)
        with mock.patch('traduccion.views_aprendizaje._tts_publico', return_value=False), \
             mock.patch.object(SintesisVozView, 'permission_classes', []):
            return SintesisVozView.as_view()(req)

    def test_usuario_normal_no_ve_la_voz(self):
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user('comunidad', password='x')
        r = self._get(u, estado='1')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['kogui']['disponible'])
        self.assertTrue(r.data.get('en_pruebas'))
        r = self._get(u, lengua='Kogui', texto='nuge')
        self.assertEqual(r.status_code, 404)

    def test_superusuario_pasa_al_servicio(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        su = get_user_model().objects.create_superuser('admin', 'a@a.co', 'x')
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = b'{"kogui": {"disponible": true}}'
        with mock.patch('urllib.request.urlopen', return_value=fake):
            r = self._get(su, estado='1')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['kogui']['disponible'])
