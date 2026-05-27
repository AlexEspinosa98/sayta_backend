from rest_framework import serializers


class TraducirRequestSerializer(serializers.Serializer):
    texto = serializers.CharField(
        help_text='Texto a traducir.'
    )
    lengua_id = serializers.IntegerField(
        help_text='ID de la lengua indígena.'
    )
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
    probabilidad = serializers.FloatField(
        help_text='Probabilidad relativa entre los resultados retornados (suma 100 %).'
    )
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
    probabilidad = serializers.FloatField(help_text='Probabilidad relativa sobre los resultados retornados.')


class TraducirResponseSerializer(serializers.Serializer):
    texto_entrada = serializers.CharField()
    lengua = LenguaInfoSerializer()
    embedding = EmbeddingInfoSerializer()
    direccion = serializers.CharField(
        help_text='Dirección de la traducción, p. ej. "es→iku" o "iku→es".'
    )
    conclusion = ConclusionSerializer(
        help_text='Resultado con mayor probabilidad. Es la traducción más probable.'
    )
    resultados = ResultadoTraduccionSerializer(many=True)
