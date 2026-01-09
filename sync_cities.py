from datetime import datetime
import logging
from supabase_client import get_supabase_client

def sync_cities(api_cities_list, db_cities_list, deactivate_missing_cities=True):
    logging.info('--- Iniciando Sync Cities (Add New / Deactivate Old) ---')

    summary = {
        "processedApiCities": len(api_cities_list) if isinstance(api_cities_list, list) else 0,
        "processedDbCities": len(db_cities_list) if isinstance(db_cities_list, list) else 0,
        "newCitiesAdded": 0,
        "citiesDeactivated": 0,
        "errors": [],
    }

    if not isinstance(api_cities_list, list):
        msg = 'Input apiCitiesList no es un array válido.'
        summary['errors'].append({'operation': 'validation', 'message': msg})
        logging.error(msg)
        return summary, []

    if not isinstance(db_cities_list, list):
        msg = 'Input dbCitiesList no es un array válido.'
        summary['errors'].append({'operation': 'validation', 'message': msg})
        logging.error(msg)
        return summary, []

    if api_cities_list and not all("city" in c for c in api_cities_list):
        msg = 'Cada ciudad en apiCitiesList debe tener la propiedad "city".'
        summary['errors'].append({'operation': 'validation', 'message': msg})
        logging.error(msg)
        return summary, []

    api_city_names = set([c['city'] for c in api_cities_list])
    db_city_map = {c['api_name']: {'id': c['id'], 'is_active': c['is_active']} for c in db_cities_list}

    logging.info(f'API reporta {len(api_city_names)} ciudades. BD tiene {len(db_city_map)} ciudades registradas.')

    cities_to_insert = [
        {"name": c['city'], "api_name": c['city']}
        for c in api_cities_list if c['city'] not in db_city_map
    ]

    for c in cities_to_insert:
        logging.info(f"[NEW] Ciudad nueva detectada: {c['api_name']}")

    city_ids_to_deactivate = []
    if deactivate_missing_cities:
        for c in db_cities_list:
            if c['is_active'] and c['api_name'] not in api_city_names:
                logging.info(f"[DEACTIVATE] Ciudad para desactivar detectada: {c['api_name']} (ID: {c['id']})")
                city_ids_to_deactivate.append(c['id'])
    else:
        logging.info("Opción de desactivar ciudades ausentes está deshabilitada.")

    try:
        supabase = get_supabase_client()
        logging.info('[OK] Cliente Supabase creado para operaciones de Sync.')

        # Inserción de nuevas ciudades
        if cities_to_insert:
            logging.info(f"[SYNC] Intentando insertar {len(cities_to_insert)} ciudades nuevas...")
            result = supabase.table('cities').insert(cities_to_insert).execute()

            # Acceder a error y datos correctamente
            if result.error:
                logging.error(f"[ERROR] Error al insertar nuevas ciudades: {result.error['message']}")
                summary['errors'].append({
                    "operation": "insert_new",
                    "message": result.error['message'],
                    "details": result.error
                })
            else:
                inserted_count = len(result.data)
                summary['newCitiesAdded'] = inserted_count
                logging.info(f"[OK] {inserted_count} ciudades nuevas insertadas exitosamente.")
        else:
            logging.info("[OK] No hay ciudades nuevas para insertar.")

        # Desactivación de ciudades ausentes
        if city_ids_to_deactivate:
            logging.info(f"🔄 Intentando desactivar {len(city_ids_to_deactivate)} ciudades...")
            updates = {
                "is_active": False,
                "updated_at": datetime.utcnow().isoformat()
            }
            result = supabase.table('cities').update(updates).in_('id', city_ids_to_deactivate).execute()

            # Acceder a error y datos correctamente
            if result.error:
                logging.error(f"[ERROR] Error al desactivar ciudades ausentes: {result.error['message']}")
                summary['errors'].append({
                    "operation": "deactivate_old",
                    "message": result.error['message'],
                    "details": result.error
                })
            else:
                summary['citiesDeactivated'] = len(city_ids_to_deactivate)
                logging.info(f"[OK] {summary['citiesDeactivated']} ciudades desactivadas exitosamente.")
        elif deactivate_missing_cities:
            logging.info("[OK] No hay ciudades para desactivar.")

        # Actualizar la lista de ciudades después de la sincronización
        updated_db_cities_list = supabase.table('cities').select('id', 'api_name', 'is_active', 'last_successful_update_at', 'last_update_status').execute().data

        logging.info('--- Finalizando Sync Cities ---')
        logging.info(f'Resumen: {summary}')
        return summary, updated_db_cities_list

    except Exception as e:
        logging.error(f"[ERROR] Error general durante la sincronizacion: {str(e)}")
        summary['errors'].append({"operation": "general_supabase", "message": str(e)})
        return summary, []


