import zipfile
import lxml.etree as ET
from datetime import datetime
from utils.database import HealthRecord
import os

def extract_and_parse(zip_path, session, status_text=None):
    extract_dir = "extracted_health_data"
    os.makedirs(extract_dir, exist_ok=True)

    xml_path = None
    if status_text:
        status_text.text("Extracting export.xml from zip...")

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            if file_info.filename.endswith('export.xml'):
                zip_ref.extract(file_info, extract_dir)
                xml_path = os.path.join(extract_dir, file_info.filename)
                break

    if not xml_path:
        raise ValueError("export.xml not found in the uploaded zip file.")

    if status_text:
        status_text.text("Parsing XML and saving to database...")

    context = ET.iterparse(xml_path, events=('end',), tag='Record')
    records_batch = []
    batch_size = 10000
    count = 0

    for event, elem in context:
        try:
            record_type = elem.get('type')
            if not record_type:
                continue

            record_type = record_type.replace('HKQuantityTypeIdentifier', '').replace('HKCategoryTypeIdentifier', '')

            value_str = elem.get('value')
            try:
                value = float(value_str)
            except (ValueError, TypeError):
                continue

            start_date_str = elem.get('startDate')
            end_date_str = elem.get('endDate')

            try:
                start_date = datetime.strptime(start_date_str[:19], '%Y-%m-%d %H:%M:%S')
                end_date = datetime.strptime(end_date_str[:19], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                continue

            record = HealthRecord(
                type=record_type,
                sourceName=elem.get('sourceName'),
                startDate=start_date,
                endDate=end_date,
                value=value,
                unit=elem.get('unit')
            )
            records_batch.append(record)
            count += 1

            if len(records_batch) >= batch_size:
                session.bulk_save_objects(records_batch)
                session.commit()
                records_batch = []
                if status_text:
                    status_text.text(f"Parsed and saved {count} records...")

        finally:
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

    if records_batch:
        session.bulk_save_objects(records_batch)
        session.commit()

    if status_text:
        status_text.text(f"Done! Parsed a total of {count} numeric records.")

    return True
