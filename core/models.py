"""
Core - Modelos de datos compartidos entre los tres engines.
Usa dataclasses para máxima eficiencia y tipado estricto.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional
import json


# ============================================================
# Enums compartidos
# ============================================================

class Vector(Enum):
    PLACSP = "placsp"         # Vector 1: Licitaciones desiertas / obras
    BOPI = "bopi"             # Vector 2: Stocks / Liquidaciones hidráulicas
    CONCURSAL = "concursal"   # Vector 3: Subastas BOE / Fincas con pozo
    DOGV = "dogv"             # Vector 4: Subvenciones DOGV / BDNS Generalitat
    CHJ = "chj"               # Vector 5: Radar Nuevos Clientes CHJ / BOPV (Pozos y Concesiones)


class Prioridad(Enum):
    CRITICA = "critica"       # Actuar en < 24h
    ALTA = "alta"             # Actuar en < 72h
    MEDIA = "media"           # Evaluar esta semana
    BAJA = "baja"             # Archivar / monitorizar


class EstadoOportunidad(Enum):
    DETECTADA = "detectada"
    EN_ANALISIS = "en_analisis"
    VIABLE = "viable"
    DESCARTADA = "descartada"
    ESCRITO_ENVIADO = "escrito_enviado"
    ADJUDICADA = "adjudicada"
    COMPLETADA = "completada"


# ============================================================
# Vector 1: Licitación Desierta
# ============================================================

@dataclass
class LicitacionDesierta:
    """Contrato público resuelto como desierto en PLACSP."""
    id: str                                  # ID único del expediente
    titulo: str = ""
    organo_contratacion: str = ""            # Ayuntamiento / Consellería / etc.
    presupuesto_base: float = 0.0            # PBL (sin IVA)
    cpv_codigo: str = ""                     # Código CPV principal
    cpv_descripcion: str = ""
    fecha_resolucion: Optional[datetime] = None
    url_pliego_tecnico: str = ""             # URL al PPT (PDF)
    url_pliego_administrativo: str = ""      # URL al PCAP (PDF)
    url_expediente: str = ""                 # URL al expediente en PLACSP
    provincia: str = ""
    comunidad_autonoma: str = ""
    tipo_contrato: str = ""                  # Servicios / Suministros / Obras
    procedimiento: str = ""                  # Abierto / Simplificado / etc.

    # Campos calculados por el engine
    margen_estimado: float = 0.0
    viabilidad_score: float = 0.0            # 0.0 a 1.0
    requisitos_solvencia: list = field(default_factory=list)
    estado: EstadoOportunidad = EstadoOportunidad.DETECTADA
    prioridad: Prioridad = Prioridad.MEDIA
    notas: str = ""
    fecha_deteccion: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['estado'] = self.estado.value
        d['prioridad'] = self.prioridad.value
        d['fecha_resolucion'] = self.fecha_resolucion.isoformat() if self.fecha_resolucion else None
        d['fecha_deteccion'] = self.fecha_deteccion.isoformat()
        return d


# ============================================================
# Vector 2: Marca Caducada
# ============================================================

@dataclass
class MarcaCaducada:
    """Marca registrada en OEPM cuya protección ha caducado por impago."""
    id: str                                  # Número de registro OEPM
    denominacion: str = ""                   # Nombre de la marca
    titular_anterior: str = ""
    clases_niza: list = field(default_factory=list)  # Clases de Niza
    fecha_concesion: Optional[datetime] = None
    fecha_caducidad: Optional[datetime] = None
    motivo_caducidad: str = ""               # "Falta de pago de tasas"
    tipo: str = ""                           # "Marca" / "Nombre comercial"

    # Campos de enriquecimiento
    dominio_es_disponible: Optional[bool] = None
    dominio_com_disponible: Optional[bool] = None
    busquedas_mensuales: int = 0
    backlinks_count: int = 0
    domain_authority: float = 0.0
    wayback_snapshots: int = 0
    antiguedad_anos: int = 0
    sector: str = ""

    # Campos calculados
    valor_estimado: float = 0.0
    viabilidad_score: float = 0.0
    riesgo_mala_fe: str = ""                 # "bajo" / "medio" / "alto"
    estado: EstadoOportunidad = EstadoOportunidad.DETECTADA
    prioridad: Prioridad = Prioridad.MEDIA
    notas: str = ""
    fecha_deteccion: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['estado'] = self.estado.value
        d['prioridad'] = self.prioridad.value
        d['fecha_concesion'] = self.fecha_concesion.isoformat() if self.fecha_concesion else None
        d['fecha_caducidad'] = self.fecha_caducidad.isoformat() if self.fecha_caducidad else None
        d['fecha_deteccion'] = self.fecha_deteccion.isoformat()
        return d


# ============================================================
# Vector 3: Lote Concursal
# ============================================================

@dataclass
class LoteConcursal:
    """Lote de activos en liquidación judicial de microempresa."""
    id: str                                  # ID del lote en la plataforma
    titulo: str = ""
    descripcion: str = ""
    categoria: str = ""
    deudor: str = ""                         # Razón social del deudor
    juzgado: str = ""
    numero_procedimiento: str = ""
    precio_salida: float = 0.0               # € precio de salida
    precio_actual: float = 0.0               # € precio actual (tras rebajas)
    tramo_actual: int = 0                    # Tramo de rebaja (1-4)
    fecha_inicio_subasta: Optional[datetime] = None
    fecha_fin_subasta: Optional[datetime] = None
    url_subasta: str = ""
    provincia: str = ""
    fotos_urls: list = field(default_factory=list)

    # Campos de análisis
    hardware_detectado: list = field(default_factory=list)  # Modelos identificados
    valor_mercado_estimado: float = 0.0      # Valor en mercado secundario
    margen_estimado: float = 0.0
    clasificacion_corregida: str = ""        # Categoría real vs. la del deudor
    keywords_encontradas: list = field(default_factory=list)

    # Campos calculados
    viabilidad_score: float = 0.0
    estado: EstadoOportunidad = EstadoOportunidad.DETECTADA
    prioridad: Prioridad = Prioridad.MEDIA
    notas: str = ""
    fecha_deteccion: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['estado'] = self.estado.value
        d['prioridad'] = self.prioridad.value
        d['fecha_inicio_subasta'] = self.fecha_inicio_subasta.isoformat() if self.fecha_inicio_subasta else None
        d['fecha_fin_subasta'] = self.fecha_fin_subasta.isoformat() if self.fecha_fin_subasta else None
        d['fecha_deteccion'] = self.fecha_deteccion.isoformat()
        return d


# ============================================================
# Modelo unificado de alerta
# ============================================================

@dataclass
class Alerta:
    """Alerta unificada para el dashboard y notificaciones."""
    id: str
    vector: Vector
    titulo: str
    resumen: str
    prioridad: Prioridad
    valor_estimado: float = 0.0
    viabilidad_score: float = 0.0
    url: str = ""
    datos_raw: str = ""                      # JSON serializado del modelo original
    estado: EstadoOportunidad = EstadoOportunidad.DETECTADA
    fecha_creacion: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'vector': self.vector.value,
            'titulo': self.titulo,
            'resumen': self.resumen,
            'prioridad': self.prioridad.value,
            'valor_estimado': self.valor_estimado,
            'viabilidad_score': self.viabilidad_score,
            'url': self.url,
            'estado': self.estado.value,
            'fecha_creacion': self.fecha_creacion.isoformat(),
        }
