"""FLEXML builders/parsers."""
import xml.etree.ElementTree as ET

def build_panel_summary_command() -> str:
    return ('<FLEXML_CMD VER="1.0" PANEL_USERNAME="FlexC" PANEL_PASSWORD="FlexC">'
            '<CMD_GET_PANEL_SUMMARY /></FLEXML_CMD>')

def build_zone_status_batch(zone_ids):
    body = "".join(f'<CMD_GET_ZONE_STATUS ZONE_ID="{z}" />' for z in zone_ids)
    return f'<FLEXML_CMD VER="1.0" PANEL_USERNAME="FlexC" PANEL_PASSWORD="FlexC">{body}</FLEXML_CMD>'

def build_area_status_batch(area_ids):
    body = "".join(f'<CMD_GET_AREA_STATUS AREA_ID="{a}" />' for a in area_ids)
    return f'<FLEXML_CMD VER="1.0" PANEL_USERNAME="FlexC" PANEL_PASSWORD="FlexC">{body}</FLEXML_CMD>'
