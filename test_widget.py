"""
test_widget.py
---------------
Verifica que el widget de captura rápida (widget/captura_rapida.html) pueda
conectarse a Supabase y operar con la anon key exactamente como lo hace el
HTML en el navegador: lee categorías, usuarios, cuentas y tarjetas, inserta
una transacción de prueba y la borra.

Uso:
    python test_widget.py

Lee SUPABASE_URL y SUPABASE_ANON_KEY de las variables de entorno; si no
están definidas, las pide por teclado.
"""

import os
import sys
from datetime import date

import requests


def pedir_credenciales() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL") or input("SUPABASE_URL: ").strip()
    key = os.environ.get("SUPABASE_ANON_KEY") or input("SUPABASE_ANON_KEY: ").strip()
    if not url or not key:
        print("❌ ERROR: SUPABASE_URL y SUPABASE_ANON_KEY son obligatorios.")
        sys.exit(1)
    return url.rstrip("/"), key


def headers(key: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def leer_tabla(url: str, key: str, tabla: str, params: dict) -> list:
    resp = requests.get(f"{url}/rest/v1/{tabla}", headers=headers(key), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main():
    print("Test de conexión — widget de captura rápida\n")
    url, key = pedir_credenciales()

    paso_actual = "conexión inicial"
    try:
        paso_actual = "leer categorías"
        print("1. Leyendo categorías...")
        categorias = leer_tabla(
            url, key, "categoria",
            {"select": "id,nombre,tipo", "tipo": "eq.gasto", "activa": "eq.1"},
        )
        print(f"   {len(categorias)} categorías de gasto encontradas.")

        paso_actual = "leer usuarios"
        print("2. Leyendo usuarios...")
        usuarios = leer_tabla(url, key, "usuario", {"select": "id,nombre"})
        print(f"   {len(usuarios)} usuarios encontrados.")

        paso_actual = "leer cuentas"
        print("3. Leyendo cuentas...")
        cuentas = leer_tabla(
            url, key, "cuenta",
            {"select": "id,nombre,usuario_id", "activa": "eq.1"},
        )
        print(f"   {len(cuentas)} cuentas encontradas.")

        paso_actual = "leer tarjetas"
        print("4. Leyendo tarjetas...")
        tarjetas = leer_tabla(
            url, key, "tarjeta_credito",
            {"select": "id,nombre,usuario_id", "activa": "eq.1"},
        )
        print(f"   {len(tarjetas)} tarjetas encontradas.")

        if not categorias:
            raise RuntimeError("No hay categorías de tipo 'gasto' activas — el widget no podría llenar el select.")
        if not cuentas and not tarjetas:
            raise RuntimeError("No hay cuentas ni tarjetas activas — el widget no tendría 'medio' para elegir.")

        usuario_id = cuentas[0]["usuario_id"] if cuentas else tarjetas[0]["usuario_id"]
        cuenta_id = cuentas[0]["id"] if cuentas else None
        tarjeta_id = tarjetas[0]["id"] if not cuentas else None

        paso_actual = "insertar transacción de prueba"
        print("5. Insertando transacción de prueba...")
        payload = {
            "usuario_id": usuario_id,
            "cuenta_id": cuenta_id,
            "tarjeta_id": tarjeta_id,
            "categoria_id": categorias[0]["id"],
            "monto": 1.00,
            "fecha": date.today().isoformat(),
            "descripcion": "[TEST_WIDGET]",
            "tipo": "gasto",
            "notas": "Insertado automáticamente por test_widget.py",
            "meses_sin_intereses": 0,
            "monto_por_mes": 0,
        }
        resp = requests.post(
            f"{url}/rest/v1/transaccion",
            headers={**headers(key), "Prefer": "return=representation"},
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        insertadas = resp.json()
        if not insertadas:
            raise RuntimeError(
                "El INSERT no devolvió la fila creada — revisa la policy "
                "'test_widget_select' descrita en IMPLEMENTACION_ESTA_SEMANA.md."
            )
        tx_id = insertadas[0]["id"]
        print(f"   Transacción de prueba creada (id={tx_id}).")

        paso_actual = "borrar transacción de prueba"
        print("6. Borrando transacción de prueba...")
        resp = requests.delete(
            f"{url}/rest/v1/transaccion",
            headers=headers(key),
            params={"id": f"eq.{tx_id}", "descripcion": "eq.[TEST_WIDGET]"},
            timeout=10,
        )
        resp.raise_for_status()
        print("   Transacción de prueba borrada.")

        print("\n✅ TODO OK — el widget puede leer catálogos e insertar gastos correctamente.")

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ ERROR en el paso '{paso_actual}':")
        print(f"   HTTP {e.response.status_code} — {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR en el paso '{paso_actual}':")
        print(f"   {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
