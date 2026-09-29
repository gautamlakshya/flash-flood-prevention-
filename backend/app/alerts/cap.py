from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

def generate_cap_xml(
    identifier: str,
    sender: str,
    event: str,
    urgency: str,
    severity: str,
    certainty: str,
    headline: str,
    description: str,
    instruction: str,
    polygon_coordinates: str,
    area_desc: str
) -> str:
    """
    Generates a CAP v1.2 compliant XML string.
    """
    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    
    # Root element
    alert = ET.Element("alert", xmlns="urn:oasis:names:tc:emergency:cap:1.2")
    
    ET.SubElement(alert, "identifier").text = identifier
    ET.SubElement(alert, "sender").text = sender
    ET.SubElement(alert, "sent").text = now_str
    ET.SubElement(alert, "status").text = "Actual" # or Test/Exercise
    ET.SubElement(alert, "msgType").text = "Alert"
    ET.SubElement(alert, "scope").text = "Public"
    
    info = ET.SubElement(alert, "info")
    ET.SubElement(info, "category").text = "Met" # Meteorological
    ET.SubElement(info, "event").text = event
    ET.SubElement(info, "urgency").text = urgency
    ET.SubElement(info, "severity").text = severity
    ET.SubElement(info, "certainty").text = certainty
    ET.SubElement(info, "effective").text = now_str
    
    ET.SubElement(info, "headline").text = headline
    ET.SubElement(info, "description").text = description
    ET.SubElement(info, "instruction").text = instruction
    
    area = ET.SubElement(info, "area")
    ET.SubElement(area, "areaDesc").text = area_desc
    if polygon_coordinates:
        ET.SubElement(area, "polygon").text = polygon_coordinates
        
    raw_xml = ET.tostring(alert, 'utf-8')
    parsed = minidom.parseString(raw_xml)
    return parsed.toprettyxml(indent="  ")
