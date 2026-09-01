"""
Небольшой сервис для работы с материалами.
Файлы не хранятся на сервере — используется Telegram file_id.
"""
import database


def get_material(slug: str):
    return database.get_material_by_slug(slug)


def list_materials():
    return database.list_active_materials()


def create_material(slug: str, title: str, description: str, file_id: str, file_type: str):
    return database.add_material(slug, title, description, file_id, file_type)
