"""경로 설정. 원본 ISO 위치는 환경변수 RC_ISO 로 바꿀 수 있다
(기본: 저장소 폴더의 상위 폴더에 있는 'Ratchet & Clank (Japan).iso')."""
import os
TOOLS = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(TOOLS)
ROOT = os.path.dirname(WORK)
ISO = os.environ.get('RC_ISO', os.path.join(ROOT, 'Ratchet & Clank (Japan).iso'))
OUT_ISO = os.environ.get('RC_OUT', os.path.join(os.path.dirname(ISO), 'Ratchet & Clank (Korean).iso'))
FONT_DIR = os.environ.get('RC_FONTS', ROOT)
