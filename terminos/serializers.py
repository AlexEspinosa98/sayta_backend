from rest_framework import serializers

from .models import EmbeddingVersion, Lengua, TerminoEs, TerminoLeng


# ---------------------------------------------------------------------------
# Lengua
# ---------------------------------------------------------------------------


class LenguaSerializer(serializers.ModelSerializer):
    total_terminos = serializers.SerializerMethodField()
    embedding_activo = serializers.SerializerMethodField()

    class Meta:
        model = Lengua
        fields = [
            'id', 'codigo', 'nombre', 'descripcion', 'activa',
            'total_terminos', 'embedding_activo',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_terminos(self, obj):
        return obj.terminos.filter(activo=True).count()

    def get_embedding_activo(self, obj):
        ev = obj.get_active_embedding()
        if ev:
            return {'id': str(ev.id), 'version': ev.version, 'num_terminos': ev.num_terminos}
        return None


class LenguaSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lengua
        fields = ['id', 'codigo', 'nombre']


# ---------------------------------------------------------------------------
# TerminoEs
# ---------------------------------------------------------------------------


class TerminoEsSerializer(serializers.ModelSerializer):
    traducciones_count = serializers.SerializerMethodField()

    class Meta:
        model = TerminoEs
        fields = ['id', 'termino', 'traducciones_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_traducciones_count(self, obj):
        return obj.traducciones.filter(activo=True).count()


# ---------------------------------------------------------------------------
# TerminoLeng
# ---------------------------------------------------------------------------


class TerminoLengSerializer(serializers.ModelSerializer):
    lengua_detail = LenguaSimpleSerializer(source='lengua', read_only=True)
    termino_es_detail = serializers.SerializerMethodField()

    class Meta:
        model = TerminoLeng
        fields = [
            'id',
            'termino_es', 'termino_es_detail',
            'lengua', 'lengua_detail',
            'termino', 'definicion', 'pos',
            'sinonimos', 'ejemplos', 'tipo_morfema',
            'activo', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_termino_es_detail(self, obj):
        if obj.termino_es:
            return {'id': obj.termino_es.id, 'termino': obj.termino_es.termino}
        return None

    def validate(self, attrs):
        termino = attrs.get('termino', getattr(self.instance, 'termino', None))
        lengua = attrs.get('lengua', getattr(self.instance, 'lengua', None))
        qs = TerminoLeng.objects.filter(termino=termino, lengua=lengua)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'termino': f'Ya existe un término "{termino}" para esta lengua.'}
            )
        return attrs


class TerminoLengCreateSerializer(serializers.ModelSerializer):
    """Serializer ligero para creación/actualización (sin campos calculados)."""

    class Meta:
        model = TerminoLeng
        fields = [
            'id',
            'termino_es', 'lengua',
            'termino', 'definicion', 'pos',
            'sinonimos', 'ejemplos', 'tipo_morfema',
            'activo',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        termino = attrs.get('termino', getattr(self.instance, 'termino', None))
        lengua = attrs.get('lengua', getattr(self.instance, 'lengua', None))
        qs = TerminoLeng.objects.filter(termino=termino, lengua=lengua)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'termino': f'Ya existe un término "{termino}" para esta lengua.'}
            )
        return attrs


# ---------------------------------------------------------------------------
# EmbeddingVersion
# ---------------------------------------------------------------------------


class EmbeddingVersionSerializer(serializers.ModelSerializer):
    lengua_detail = LenguaSimpleSerializer(source='lengua', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EmbeddingVersion
        fields = [
            'id', 'lengua', 'lengua_detail',
            'version', 'model_name',
            'status', 'status_display', 'is_active',
            'num_terminos', 'error_message',
            'task_id',
            'created_at', 'completed_at',
        ]
        read_only_fields = [
            'id', 'version', 'status', 'is_active',
            'num_terminos', 'error_message',
            'embeddings_path', 'faiss_path', 'metadata_path',
            'task_id', 'created_at', 'completed_at',
        ]


class GenerarEmbeddingSerializer(serializers.Serializer):
    """Payload para disparar la generación de un embedding."""

    lengua_id = serializers.IntegerField()
    model_name = serializers.CharField(
        required=False,
        default='intfloat/multilingual-e5-base',
        max_length=255,
    )
