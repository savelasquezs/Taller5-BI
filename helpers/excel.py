import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def texto(valor):
    if valor is None:
        return None
    limpio = re.sub(r"\s+", " ", str(valor)).strip()
    return limpio or None


def etiqueta(valor):
    limpio = texto(valor)
    return limpio.casefold() if limpio else ""


def opcional(valor):
    return None if etiqueta(valor) in {"", "no aplica", "[19] no aplica", "sin especificar"} else texto(valor)


def numero(valor, campo, obligatorio=False):
    if texto(valor) is None:
        if obligatorio:
            raise ValueError(f"Falta {campo}")
        return None
    if isinstance(valor, bool):
        raise ValueError(f"{campo}: se esperaba un número")
    try:
        resultado = Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"{campo}: número inválido {valor!r}") from None
    if not resultado.is_finite() or resultado < 0:
        raise ValueError(f"{campo}: debe ser un número finito no negativo")
    return resultado


def entero(valor, campo):
    resultado = numero(valor, campo)
    if resultado is not None and (resultado != resultado.to_integral_value() or resultado <= 0):
        raise ValueError(f"{campo}: debe ser un entero positivo")
    return int(resultado) if resultado is not None else None


def fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(valor), formato).date()
        except ValueError:
            pass
    raise ValueError(f"Fecha inválida: {valor!r}")


def huella(valor):
    def serializar(elemento):
        if isinstance(elemento, Decimal):
            return str(elemento.normalize())
        if isinstance(elemento, (date, datetime)):
            return elemento.isoformat()
        raise TypeError(f"Tipo no soportado: {type(elemento).__name__}")

    contenido = json.dumps(valor, sort_keys=True, ensure_ascii=False, default=serializar)
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()
