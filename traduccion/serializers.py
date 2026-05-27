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
    termino = serializers.CharField(allow_null=True)
    definicion = serializers.CharField(allow_blank=True)
    score = serializers.FloatField(allow_null=True, help_text='Similitud coseno (0-1).')


class EmbeddingInfoSerializer(serializers.Serializer):
    version_id = serializers.UUIDField()
    version = serializers.CharField()
    modelo = serializers.CharField()
    num_terminos = serializers.IntegerField()


class LenguaInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    nombre = serializers.CharField()


class TraducirResponseSerializer(serializers.Serializer):
    texto_entrada = serializers.CharField()
    lengua = LenguaInfoSerializer()
    embedding = EmbeddingInfoSerializer()
    direccion = serializers.CharField(
        help_text='Dirección detectada automáticamente, p. ej. "es→iku" o "iku→es".'
    )
    resultados = ResultadoTraduccionSerializer(many=True)
