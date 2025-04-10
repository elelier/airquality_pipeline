from supabase import create_client, Client
from datetime import datetime




def sync_cities(api_cities_list, db_cities_list, supabase_url, supabase_service_role_key, deactivate_missing_cities=True, logging=print):
    logging('--- Iniciando Sync Cities (Add New / Deactivate Old) ---')

    summary = {
        "processedApiCities": len(api_cities_list) if isinstance(api_cities_list, list) else 0,
        "processedDbCities": len(db_cities_list) if isinstance(db_cities_list, list) else 0,
        "newCitiesAdded": 0,
        "citiesDeactivated": 0,
        "errors": [],
    }

    if not supabase_url or not supabase_service_role_key:
        msg = 'Supabase URL/Key faltantes.'
        summary['errors'].append({'operation': 'validation', 'message': msg})
        logging(msg)
        return summary

    if not isinstance(api_cities_list, list):
        msg = 'Input apiCitiesList no es un array válido.'
        summary['errors'].append({'operation': 'validation', 'message': msg})
        logging(msg)
        return summary

    if not isinstance(db_cities_list, list):
        msg = 'Input dbCitiesList no es un array válido.'
        summary['errors'].append({'operation': 'validation', 'message': msg})
        logging(msg)
        return summary

    if api_cities_list and not all("city" in c for c in api_cities_list):
        msg = 'Cada ciudad en apiCitiesList debe tener la propiedad "city".'
        summary['errors'].append({'operation': 'validation', 'message': msg})
        logging(msg)
        return summary

    api_city_names = set([c['city'] for c in api_cities_list])
    db_city_map = {c['api_name']: {'id': c['id'], 'is_active': c['is_active']} for c in db_cities_list}

    logging(f'API reporta {len(api_city_names)} ciudades. BD tiene {len(db_city_map)} ciudades registradas.')

    cities_to_insert = [
        {"name": c['city'], "api_name": c['city']}
        for c in api_cities_list if c['city'] not in db_city_map
    ]

    for c in cities_to_insert:
        logging(f"🆕 Ciudad nueva detectada: {c['api_name']}")

    city_ids_to_deactivate = []
    if deactivate_missing_cities:
        for c in db_cities_list:
            if c['is_active'] and c['api_name'] not in api_city_names:
                logging(f"🛑 Ciudad para desactivar detectada: {c['api_name']} (ID: {c['id']})")
                city_ids_to_deactivate.append(c['id'])
    else:
        logging("Opción de desactivar ciudades ausentes está deshabilitada.")

    try:
        supabase: Client = create_client(supabase_url, supabase_service_role_key)
        logging('✅ Cliente Supabase creado para operaciones de Sync.')

        # Inserción de nuevas ciudades
        if cities_to_insert:
            logging(f"🔄 Intentando insertar {len(cities_to_insert)} ciudades nuevas...")
            result = supabase.table('cities').insert(cities_to_insert).execute()
            if result.get('error'):
                logging(f"❌ Error al insertar nuevas ciudades: {result['error']['message']}")
                summary['errors'].append({
                    "operation": "insert_new",
                    "message": result['error']['message'],
                    "details": result['error']
                })
            else:
                inserted_count = len(result.get('data', []))
                summary['newCitiesAdded'] = inserted_count
                logging(f"✅ {inserted_count} ciudades nuevas insertadas exitosamente.")
        else:
            logging("✅ No hay ciudades nuevas para insertar.")

        # Desactivación de ciudades ausentes
        if city_ids_to_deactivate:
            logging(f"🔄 Intentando desactivar {len(city_ids_to_deactivate)} ciudades...")
            updates = {
                "is_active": False,
                "updated_at": datetime.utcnow().isoformat()
            }
            result = supabase.table('cities').update(updates).in_('id', city_ids_to_deactivate).execute()
            if result.get('error'):
                logging(f"❌ Error al desactivar ciudades ausentes: {result['error']['message']}")
                summary['errors'].append({
                    "operation": "deactivate_old",
                    "message": result['error']['message'],
                    "details": result['error']
                })
            else:
                summary['citiesDeactivated'] = len(city_ids_to_deactivate)
                logging(f"✅ {summary['citiesDeactivated']} ciudades desactivadas exitosamente.")
        elif deactivate_missing_cities:
            logging("✅ No hay ciudades para desactivar.")

        # Actualizar la lista de ciudades después de la sincronización
        updated_db_cities_list = supabase.table('cities').select('id', 'api_name', 'is_active', 'last_successful_update_at', 'last_update_status').execute().data

        logging('--- Finalizando Sync Cities ---')
        logging(f'Resumen: {summary}')
        return summary, updated_db_cities_list

    except Exception as e:
        logging(f"❌ Error general durante la sincronización: {str(e)}")
        summary['errors'].append({"operation": "general_supabase", "message": str(e)})
        return summary, []

