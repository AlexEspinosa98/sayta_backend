import logging
import os
import sys
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)

_COMANDOS_SIN_PRECARGA = {'migrate', 'makemigrations', 'shell', 'collectstatic', 'dumpdata', 'loaddata', 'test', 'check', 'evaluar_traductor', 'createsuperuser', 'entrenar_worker'}


class TraduccionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'traduccion'
    verbose_name = 'Traducción'

    def ready(self):
        if any(c in sys.argv for c in _COMANDOS_SIN_PRECARGA) or os.environ.get('SAYTA_SIN_PRECARGA') == '1':
            return
        threading.Thread(target=_precalentar, name='traduccion-precarga', daemon=True).start()


def _precalentar():
    """Carga el modelo de embeddings, los índices FAISS y el índice léxico al arrancar,
    para que la primera traducción no tarde varios segundos."""
    try:
        from terminos.models import Lengua
        from translator_api.search_engine import MultiLanguageSearchEngine
        from traduccion import lexico
        engine = MultiLanguageSearchEngine.get_instance()
        for codigo in engine.available_languages():
            try:
                engine.search('hola', language_code=codigo, top_k=1)
            except Exception as exc:
                logger.warning('Precarga semántica %s: %s', codigo, exc)
        for l in Lengua.objects.filter(activa=True):
            lexico.indice(l.codigo)
        logger.info('Traductor precargado (%d lenguas)', len(engine.available_languages()))
    except Exception as exc:
        logger.warning('No se pudo precargar el traductor: %s', exc)
