from rest_framework import serializers


class TraducirRequestSerializer(serializers.Serializer):
    texto = serializers.CharField(
        help_text='Texto a traducir.'
    )
    lengua_id = serializers.IntegerField(
        help_text='ID de la lengua indígena.'
    )
    verificar = serializers.BooleanField(required=False, default=True, help_text='Pasar el resultado por el agente verificador (modelo de lenguaje local).')
    direccion = serializers.ChoiceField(
        choices=['es_a_lengua', 'lengua_a_es'],
        help_text=(
            '"es_a_lengua": el texto está en español y se busca en la lengua indígena. '
            '"lengua_a_es": el texto está en la lengua indígena y se busca su equivalente en español.'
        ),
    )


class ResultadoTraduccionSerializer(serializers.Serializer):
    termino = serializers.CharField(allow_null=True, help_text='Término en la lengua indígena.')
    termino_es = serializers.CharField(allow_blank=True, help_text='Equivalente en español.')
    definicion = serializers.CharField(allow_blank=True, help_text='Definición en español.')
    score = serializers.FloatField(allow_null=True, help_text='Similitud coseno (0–1).')
    probabilidad = serializers.FloatField(help_text='Igual a confianza (compatibilidad).')
    confianza = serializers.IntegerField(help_text='Confianza absoluta 0–100: 100 = coincidencia exacta con el glosario.')
    nivel = serializers.CharField(help_text="exacta | aproximada | parcial | alta | media | baja")
    fuente = serializers.CharField(help_text="glosario | patrón | semántica")
    nota = serializers.CharField(allow_blank=True, required=False)
    hipotesis = serializers.BooleanField(required=False, help_text='True si la entrada es una hipótesis aún no validada con hablantes.')
    verificado = serializers.BooleanField(required=False)
    audio_ejemplo = serializers.BooleanField(required=False, help_text='True si existe una grabación real de la comunidad con esta transcripción.')
    mejor_coincidencia = serializers.BooleanField(
        help_text='True en el resultado con mayor probabilidad (el que más sentido tiene).'
    )
    coincidencia = serializers.CharField(
        allow_blank=True,
        help_text='Sub-consulta que produjo este resultado (frase, bigrama o token).',
    )


class EmbeddingInfoSerializer(serializers.Serializer):
    version_id = serializers.UUIDField()
    version = serializers.CharField()
    modelo = serializers.CharField()
    num_terminos = serializers.IntegerField()


class LenguaInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre = serializers.CharField()


class ConclusionSerializer(serializers.Serializer):
    termino = serializers.CharField(help_text='Término en la lengua indígena con mayor probabilidad.')
    termino_es = serializers.CharField(help_text='Equivalente en español.')
    definicion = serializers.CharField(help_text='Definición en español.')
    probabilidad = serializers.FloatField(help_text='Igual a confianza (compatibilidad).')
    confianza = serializers.IntegerField(required=False)
    nivel = serializers.CharField(required=False)
    fuente = serializers.CharField(required=False)


class TraducirResponseSerializer(serializers.Serializer):
    texto_entrada = serializers.CharField()
    lengua = LenguaInfoSerializer()
    embedding = EmbeddingInfoSerializer()
    direccion = serializers.CharField(
        help_text='Dirección de la traducción, p. ej. "es→iku" o "iku→es".'
    )
    conclusion = ConclusionSerializer(
        allow_null=True,
        help_text='Resultado con mayor probabilidad. Es la traducción más probable.'
    )
    resultados = ResultadoTraduccionSerializer(many=True)
    en_glosario = serializers.BooleanField(required=False, help_text='False cuando el texto no parece estar en el glosario.')
    aviso = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    consulta_id = serializers.CharField(allow_null=True, required=False, help_text='Id del registro de la consulta (para enviar la opción elegida o una corrección).')
    verificacion = serializers.DictField(allow_null=True, required=False, help_text='Resultado del agente verificador: estado (confirmada | ajustada | compuesta | sin_coincidencia | rechazada | no_concluyente | no_disponible | omitida), eleccion, traduccion_final, explicacion, confianza, sin_traducir, modelo, ms, piezas.')
