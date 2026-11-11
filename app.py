import streamlit as st
import numpy as np
import cv2
from PIL import Image
import os
import io
import base64
import inspect
from packaging.version import Version

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="RetinaAI - Standalone DR Screening System",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------
# STREAMLIT VERSION / FEATURE CHECKS
# The header is built differently depending on what the installed
# Streamlit supports, so the same file runs on older and newer versions.
# ---------------------------------------------------------
ST_VERSION = Version(st.__version__)

def _supports(func, param):
    """True if the Streamlit function accepts the given keyword argument."""
    try:
        return param in inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False

# 1.39+: containers and widgets can take key=..., which adds a .st-key-<key> CSS class
USE_KEYED_HEADER = ST_VERSION >= Version("1.39.0") and _supports(st.container, "key")
# Material icons on buttons (only used on the keyed path to be safe)
# Disabled: the header CSS sets a font on every span in the button, which turns the
# Material icon into the plain word "refresh". The text arrow below looks the same everywhere.
USE_BUTTON_ICON = False
# st.columns(vertical_alignment=...) arrived in 1.36
USE_VALIGN = _supports(st.columns, "vertical_alignment")

def image_frame_html(img, alt="image"):
    """Return HTML that shows the image centered inside a fixed-size frame.
    Works on every Streamlit version (no st.image width arguments needed)."""
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img)
    img = img.convert("RGB")
    img.thumbnail((1024, 1024))  # keep the page light; display size is smaller anyway
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<div class="img-frame"><img src="data:image/jpeg;base64,{b64}" alt="{alt}"></div>'

def card_container():
    # Plain container; the card look (white, border, shadow) comes from CSS
    # so it matches .med-card exactly on every Streamlit version.
    return st.container()

# CSS selectors for the header, chosen by version:
#  - New: the keyed container is the banner, its column row is inside it.
#  - Old: no keys, so the column row is found by a hidden marker element
#         (.rai-header-marker) and the row itself becomes the banner.
if USE_KEYED_HEADER:
    BANNER_SEL = ".st-key-header_banner"
    ROW_SEL = '.st-key-header_banner [data-testid="stHorizontalBlock"]'
else:
    BANNER_SEL = 'div[data-testid="stHorizontalBlock"]:has(.rai-header-marker)'
    ROW_SEL = BANNER_SEL

# ---------------------------------------------------------
# SESSION STATE (used by "New Screening" to clear the uploader)
# ---------------------------------------------------------
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

def reset_screening():
    # Changing the uploader's key gives a fresh, empty file_uploader
    st.session_state.uploader_key += 1

# ---------------------------------------------------------
# HEADER STYLING (selectors filled in for the detected version)
# ---------------------------------------------------------
HEADER_CSS = """
    <style>
        /* Banner background, flush to the page edges */
        __BANNER__ {
            background-color: #0b1329 !important;
            margin-left: -5rem !important;
            margin-right: -5rem !important;
            margin-top: 0rem !important;
            /* Space between header and cards. Streamlit already adds
               ~16px between blocks, so a negative value pulls cards closer.
               Tweak this number: more negative = closer. */
            margin-bottom: 0.5rem !important;
            /* Top padding is larger than bottom to visually center the
               content. Tweak these if it still looks off. */
            padding: 18px 24px 12px 24px !important;
            border-bottom: 1px solid #1e293b !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2) !important;
            width: auto !important;
        }

        /* Row behaves like app_best's flex row */
        __ROW__ {
            display: flex !important;
            align-items: center !important;
            flex-wrap: nowrap !important;
            gap: 10px !important;
        }

        /* Action columns shrink to their content, and every column
           centers its content vertically */
        __ROW__ > div {
            flex: 0 0 auto !important;
            width: auto !important;
            min-width: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-self: center !important;
        }

        /* Brand column takes the remaining space */
        __ROW__ > div:first-child {
            flex: 1 1 auto !important;
        }

        __BANNER__ [data-testid="stVerticalBlock"],
        __BANNER__ [data-testid="stVerticalBlockBorderWrapper"] {
            gap: 0 !important;
            justify-content: center !important;
        }

        /* Remove Streamlit's default spacing around elements so
           nothing gets pushed up or down */
        __BANNER__ [data-testid="stElementContainer"],
        __BANNER__ [data-testid="element-container"],
        __BANNER__ [data-testid="stMarkdown"],
        __BANNER__ [data-testid="stMarkdownContainer"],
        __BANNER__ [data-testid="stSelectbox"],
        __BANNER__ [data-testid="stButton"],
        __BANNER__ .stButton {
            margin: 0 !important;
            padding: 0 !important;
        }

        __BANNER__ .header-brand {
            margin: 0 !important;
            height: 36px;
        }

        /* ---------- Model selector pill ---------- */
        __BANNER__ div[data-baseweb="select"] {
            width: 190px !important;
        }

        __BANNER__ div[data-baseweb="select"] > div {
            background-color: rgba(30, 41, 59, 0.75) !important;
            border: 1px solid #334155 !important;
            border-radius: 9999px !important;
            height: 34px !important;
            min-height: 34px !important;
            padding-left: 22px !important;
            padding-right: 6px !important;
            position: relative !important;
            cursor: pointer !important;
            box-shadow: none !important;
        }

        /* Green status dot */
        __BANNER__ div[data-baseweb="select"] > div::before {
            content: "";
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            width: 8px;
            height: 8px;
            background-color: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 6px #10b981;
        }

        __BANNER__ div[data-baseweb="select"] * {
            color: #ffffff !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        }

        __BANNER__ div[data-baseweb="select"] svg {
            fill: #ffffff !important;
        }

        /* ---------- New Screening pill ---------- */
        __BANNER__ button {
            background-color: rgba(30, 41, 59, 0.75) !important;
            border: 1px solid #334155 !important;
            border-radius: 9999px !important;
            color: #ffffff !important;
            padding: 0 14px !important;
            height: 34px !important;
            min-height: 34px !important;
            display: flex !important;
            align-items: center !important;
            gap: 6px !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
            white-space: nowrap !important;
        }

        /* Same font as the model selector */
        __BANNER__ button p,
        __BANNER__ button span {
            color: #ffffff !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
            margin: 0 !important;
            line-height: 1 !important;
        }

        __BANNER__ button:hover {
            background-color: rgba(51, 65, 85, 0.9) !important;
            border-color: #475569 !important;
        }

        __BANNER__ button:focus:not(:active) {
            border-color: #334155 !important;
            color: #ffffff !important;
        }
    </style>
"""
st.markdown(
    HEADER_CSS.replace("__BANNER__", BANNER_SEL).replace("__ROW__", ROW_SEL),
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# GENERAL STYLING & CUSTOM CARD UI
# ---------------------------------------------------------
st.markdown("""
    <style>
        .stApp {
            background-color: #f8fafc !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        }

        header[data-testid="stHeader"], footer {
            display: none !important;
        }

        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 2rem !important;
            max-width: 1280px !important;
            margin: 0 auto !important;
        }

        .rai-header-marker {
            display: none !important;
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .eye-box {
            background-color: #0284c7;
            width: 36px;
            height: 36px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .brand-text {
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .title-main {
            color: #ffffff;
            font-size: 17px;
            font-weight: 700;
            margin: 0;
            padding: 0;
            line-height: 1.1;
        }

        .title-sub {
            color: #94a3b8;
            font-size: 11px;
            margin: 2px 0 0 0;
            padding: 0;
            line-height: 1.0;
        }

        /* Dropdown list (rendered outside the header, so styled globally) */
        div[data-baseweb="popover"] ul {
            background-color: #0f172a !important;
        }
        div[data-baseweb="popover"] li {
            color: #ffffff !important;
            font-size: 13px !important;
        }
        div[data-baseweb="popover"] li:hover,
        div[data-baseweb="popover"] li[aria-selected="true"] {
            background-color: #1e293b !important;
        }

        /* CARD WRAPPERS */
        .med-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 14px;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
            margin-bottom: 8px;
        }

        /* One spacing value for all card content. It matches the card's
           inner padding, so the gap between sections equals the gap
           to the card edge. Change it here to adjust every card. */
        :root {
            --card-gap: 14px;
        }

        .card-header-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: var(--card-gap);
        }

        /* Streamlit adds its own padding to h1-h6 inside st.markdown,
           which created the extra space under the card titles */
        h3.card-title,
        .stMarkdown h3.card-title {
            font-size: 13px !important;
            font-weight: 700 !important;
            color: #475569 !important;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1.3 !important;
        }

        /* Hide Streamlit's hover link icon on headings */
        .med-card [data-testid="stHeaderActionElements"],
        .card-header-row [data-testid="stHeaderActionElements"],
        .med-card h2 a, .med-card h3 a,
        .card-header-row h3 a {
            display: none !important;
        }

        .card-subtitle-tag {
            font-size: 12px;
            color: #94a3b8;
            font-weight: 500;
        }

        /* RETINAL IMAGE INPUT BOX */
        .uploader-wrapper {
            position: relative;
            width: 100%;
        }

        .custom-drop-overlay {
            border: 2px dashed #cbd5e1;
            border-radius: 10px;
            background-color: #f8fafc;
            padding: 12px 12px;
            text-align: center;
            pointer-events: none;
            transition: all 0.2s ease;
        }

        .cloud-icon-circle {
            width: 38px;
            height: 38px;
            background-color: #ffffff;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 8px auto;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }

        .drop-text-primary {
            font-size: 14px;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 4px;
        }

        .drop-text-primary span {
            color: #0284c7;
            text-decoration: underline;
        }

        .drop-text-secondary {
            font-size: 12px;
            color: #94a3b8;
        }

        div[data-testid="stFileUploader"] {
            margin-top: -95px !important;
            opacity: 0 !important;
            height: 95px !important;
            cursor: pointer !important;
        }

        div[data-testid="stFileUploader"] section {
            height: 95px !important;
            padding: 0 !important;
            cursor: pointer !important;
        }

        /* DIAGNOSIS & CONFIDENCE STYLING
           Severity colours run from green (Grade 0) to red (Grade 4).
           Shared pill shape first, then one colour set per grade. */
        .diag-pill-grade-0,
        .diag-pill-grade-1,
        .diag-pill-grade-2,
        .diag-pill-grade-3,
        .diag-pill-grade-4 {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .diag-pill-grade-0 { background-color: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; } /* green  */
        .diag-pill-grade-1 { background-color: #ecfccb; color: #4d7c0f; border: 1px solid #d9f99d; } /* lime   */
        .diag-pill-grade-2 { background-color: #fef9c3; color: #a16207; border: 1px solid #fef08a; } /* yellow */
        .diag-pill-grade-3 { background-color: #ffedd5; color: #c2410c; border: 1px solid #fed7aa; } /* orange */
        .diag-pill-grade-4 { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; } /* red    */

        h2.diag-main-title,
        .stMarkdown h2.diag-main-title {
            font-size: 22px !important;
            font-weight: 800 !important;
            color: #0f172a !important;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1.2 !important;
        }

        /* Result block (badge + title + confidence) */
        .diag-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: var(--card-gap);
        }

        /* "Softmax Stage Probability Breakdown" label with divider line */
        .breakdown-label {
            font-size: 14px;
            font-weight: 700;
            color: #475569;
            border-top: 1px solid #f1f5f9;
            padding-top: var(--card-gap);
            margin-bottom: var(--card-gap);
        }

        .confidence-ring-card {
            background-color: #f8fafc;
            border: 1px solid #f1f5f9;
            border-radius: 10px;
            padding: 2px 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .ring-circle {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            border: 2px solid #0284c7;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 10px;
            color: #0284c7;
            background-color: #ffffff;
        }

        .ring-label-title {
            font-size: 10px;
            font-weight: 800;
            color: #94a3b8;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        /* Progress Bars */
        .prob-row {
            margin-bottom: var(--card-gap);
        }
        /* No extra space after the last bar, so the bottom gap is just the card padding */
        .prob-row:last-child {
            margin-bottom: 0;
        }
        .prob-header {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            color: #475569;
            margin-bottom: 4px;
        }
        .prob-bar-bg {
            background-color: #f1f5f9;
            border-radius: 9999px;
            height: 8px;
            width: 100%;
            overflow: hidden;
        }
        .prob-bar-fill {
            background-color: #10b981;
            height: 100%;
            border-radius: 9999px;
        }

        /* GRAD-CAM PLACEHOLDERS & INNER CARDS
           The placeholder and the image frame share one fixed size,
           so the card never changes size when an image is loaded. */
        :root {
            --img-frame-h: 260px;
        }

        .img-placeholder-card,
        .img-frame {
            width: 100%;
            height: var(--img-frame-h);
            box-sizing: border-box;
            border-radius: 12px;
            background-color: #0f172a;
            overflow: hidden;
        }

        /* Image sits in the center and is scaled down to fit,
           keeping its proportions, so it never spills out */
        .img-frame {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 8px;
        }

        .img-frame img {
            max-width: 100%;
            max-height: 100%;
            width: auto;
            height: auto;
            object-fit: contain;
            display: block;
            border-radius: 8px;
        }

        .img-placeholder-card {
            border: 1px dashed #334155;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: #64748b;
            text-align: center;
            padding: 16px;
            margin: 0;
        }

        .img-label-top {
            font-size: 11px;
            font-weight: 700;
            color: #475569;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin: 0;
        }

        /* =========================================================
           STREAMLIT CONTAINERS STYLED AS CARDS (same look as .med-card)
           Each card is found by a class inside it:
             - Grad-CAM main card: .gradcam-header
             - Image cards:        .img-label-top
           ":not(:has(...))" picks the innermost container holding
           that class, so only the card itself gets styled.
           ========================================================= */
        div[data-testid="stVerticalBlock"]:has(.gradcam-header):not(:has(div[data-testid="stVerticalBlock"] .gradcam-header)),
        div[data-testid="stVerticalBlock"]:has(.img-label-top):not(:has(div[data-testid="stVerticalBlock"] .img-label-top)) {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: var(--card-gap) !important;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
            gap: var(--card-gap) !important;
            box-sizing: border-box !important;
            width: 100% !important;
        }

        /* Gap between the two image cards = same card gap */
        div[data-testid="stVerticalBlock"]:has(.gradcam-header):not(:has(div[data-testid="stVerticalBlock"] .gradcam-header)) > div [data-testid="stHorizontalBlock"],
        div[data-testid="stVerticalBlock"]:has(.gradcam-header):not(:has(div[data-testid="stVerticalBlock"] .gradcam-header)) > [data-testid="stHorizontalBlock"] {
            gap: var(--card-gap) !important;
        }

        /* =========================================================
           LOADING STATE WHILE A DIAGNOSTIC IS RUNNING
           Streamlit marks old elements as "stale" during a rerun and
           fades/blurs them. Keep every card fully visible, and blur
           only the image boxes so it's clear analysis is in progress.
           ========================================================= */
        [data-stale="true"],
        .stale-element,
        [data-testid="stElementContainer"][data-stale="true"],
        [data-testid="element-container"][data-stale="true"] {
            opacity: 1 !important;
            filter: none !important;
            transition: none !important;
        }

        [data-stale="true"] .img-frame,
        [data-stale="true"] .img-placeholder-card,
        .stale-element .img-frame,
        .stale-element .img-placeholder-card {
            filter: blur(4px);
            transition: filter 0.2s ease;
        }

        /* Keep columns from overflowing the main card */
        div[data-testid="stVerticalBlock"]:has(.gradcam-header):not(:has(div[data-testid="stVerticalBlock"] .gradcam-header)) [data-testid="stColumn"],
        div[data-testid="stVerticalBlock"]:has(.gradcam-header):not(:has(div[data-testid="stVerticalBlock"] .gradcam-header)) [data-testid="column"] {
            min-width: 0 !important;
        }

        /* Streamlit gives elements a fixed width that ignores the card's
           padding, which pushed the placeholder outside the card.
           Make every element fit inside the card instead. */
        div[data-testid="stVerticalBlock"]:has(.img-label-top):not(:has(div[data-testid="stVerticalBlock"] .img-label-top)) [data-testid="stElementContainer"],
        div[data-testid="stVerticalBlock"]:has(.img-label-top):not(:has(div[data-testid="stVerticalBlock"] .img-label-top)) [data-testid="element-container"],
        div[data-testid="stVerticalBlock"]:has(.img-label-top):not(:has(div[data-testid="stVerticalBlock"] .img-label-top)) [data-testid="stMarkdown"],
        div[data-testid="stVerticalBlock"]:has(.img-label-top):not(:has(div[data-testid="stVerticalBlock"] .img-label-top)) [data-testid="stMarkdownContainer"] {
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
        }
    </style>
""", unsafe_allow_html=True)

# Safe TensorFlow Import
try:
    import tensorflow as tf
    TF_AVAILABLE = True
except Exception as e:
    TF_AVAILABLE = False
    st.error(f"Error loading TensorFlow: {e}")

# Model Configurations (512x512)
# "input_mode" must match how each model saw images during training:
#   "raw"         -> raw pixel values 0-255 (ImageDataGenerator() with no rescale)
#   "rescale"     -> values 0-1 (ImageDataGenerator(rescale=1./255))
#   "resnet_caffe"-> tf.keras.applications.resnet50.preprocess_input
#                    (RGB->BGR and ImageNet mean subtraction, no division by 255)
MODEL_CONFIGS = {
    "ResNet-50": {
        "path": "models/resnet50_dr.keras",
        "last_conv_layer": "conv5_block3_out",
        "target_size": (512, 512),
        # Confirmed from the ResNet-50 training notebook: the generators used
        # preprocessing_function=resnet50.preprocess_input.
        "input_mode": "resnet_caffe"
    },
    "EfficientNet-B0": {
        "path": "models/efficientnetb0_dr.keras",
        "last_conv_layer": "top_activation",
        "target_size": (512, 512),
        # Trained with ImageDataGenerator() and no rescale, so it expects 0-255.
        # EfficientNet rescales internally; dividing by 255 here made every image near-black.
        "input_mode": "raw"
    },
    "DenseNet-121": {
        "path": "models/densenet121_dr.keras",
        "last_conv_layer": "relu",
        "target_size": (512, 512),
        "input_mode": "rescale"   # Training notebook: ImageDataGenerator(rescale=1./255)
    }
}


def prepare_model_input(img_rgb_uint8, input_mode):
    """Scale a Ben Graham preprocessed RGB image (0-255) the same way the
    selected model's training generator did. Returns float32, no batch axis."""
    x = img_rgb_uint8.astype(np.float32)  # astype makes a copy, so the display image is untouched
    if input_mode == "resnet_caffe":
        return tf.keras.applications.resnet50.preprocess_input(x)
    if input_mode == "rescale":
        return x / 255.0
    return x  # "raw"

DR_CLASSES = {
    0: ("GRADE 0: NORMAL (NO DR)", "No Diabetic Retinopathy Detected", "diag-pill-grade-0"),
    1: ("GRADE 1: MILD NPDR", "Mild Non-Proliferative DR", "diag-pill-grade-1"),
    2: ("GRADE 2: MODERATE NPDR", "Moderate Non-Proliferative DR", "diag-pill-grade-2"),
    3: ("GRADE 3: SEVERE NPDR", "Severe Non-Proliferative DR", "diag-pill-grade-3"),
    4: ("GRADE 4: PROLIFERATIVE DR (PDR)", "Proliferative Diabetic Retinopathy", "diag-pill-grade-4")
}

# Probability bar colour for each grade, green (Grade 0) to red (Grade 4)
GRADE_BAR_COLORS = ["#22c55e", "#84cc16", "#eab308", "#f97316", "#ef4444"]

# 1. Ben Graham Preprocessing (512x512)
def ben_graham_preprocess(img_pil, target_size=(512, 512)):
    img = np.array(img_pil)
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    img_resized = cv2.resize(img_bgr, target_size)

    img_uint8 = np.clip(img_resized, 0, 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(img_uint8, (0, 0), 10)
    enhanced = cv2.addWeighted(img_uint8, 4, blurred, -4, 128)
    return cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)

# 2. Grad-CAM Heatmap Computation
def _find_layer_and_container(model, layer_name):
    """Find a layer by name. Returns (container, nested_base):
    - (model, None) if the layer is directly in the model
      (e.g. Model(base_model.input, outputs) like the EfficientNet/ResNet notebooks)
    - (model, base) if it's inside a nested base model
      (e.g. the DenseNet file, where 'densenet121' is a single layer of the model)
    """
    try:
        model.get_layer(layer_name)
        return model, None
    except ValueError:
        pass
    for layer in model.layers:
        if hasattr(layer, "layers"):  # nested model
            try:
                layer.get_layer(layer_name)
                return model, layer
            except ValueError:
                continue
    return model, None


def _build_gradcam_model(model, layer_name):
    """Return a function x -> (conv_output, predictions)."""
    container, base = _find_layer_and_container(model, layer_name)

    if base is None:
        if layer_name not in [l.name for l in model.layers]:
            # Fallback: last layer that outputs a 4D feature map
            layer_name = [l.name for l in model.layers
                          if len(getattr(l, "output", tf.zeros([1])).shape) == 4][-1]
        grad_model = tf.keras.models.Model(
            inputs=model.inputs,
            outputs=[model.get_layer(layer_name).output, model.output]
        )
        return lambda x: grad_model(x)

    # Nested base: run the base to get the conv map, then the head layers after it
    base_model = tf.keras.models.Model(
        inputs=base.inputs,
        outputs=[base.get_layer(layer_name).output, base.output]
    )
    head_layers = model.layers[model.layers.index(base) + 1:]

    def run(x):
        conv_out, out = base_model(x)
        for layer in head_layers:
            out = layer(out, training=False)
        return conv_out, out
    return run


def make_gradcam_heatmap(img_array, model, last_conv_layer_name):
    grad_model = _build_gradcam_model(model, last_conv_layer_name)

    with tf.GradientTape() as tape:
        last_conv_layer_output, preds = grad_model(img_array)
        pred_index = tf.argmax(preds[0])
        class_channel = preds[:, pred_index]

    grads = tape.gradient(class_channel, last_conv_layer_output)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    last_conv_layer_output = last_conv_layer_output[0]
    heatmap = last_conv_layer_output @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)

    heatmap = tf.maximum(heatmap, 0) / (tf.math.reduce_max(heatmap) + 1e-10)
    return heatmap.numpy(), preds

def generate_superimposed_gradcam(img_rgb, heatmap, alpha=0.65):
    h, w, _ = img_rgb.shape
    heatmap_resized = cv2.resize(heatmap, (w, h))
    heatmap_resized = np.uint8(255 * heatmap_resized)
    heatmap_colored = cv2.applyColorMap(heatmap_resized, cv2.COLORMAP_JET)
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

    superimposed = cv2.addWeighted(img_rgb, alpha, heatmap_colored, 1 - alpha, 0)
    return superimposed

# show_spinner=False: the default "Running load_dr_model()" spinner takes the
# place of the next element on the page, which made the Classification Result
# card disappear while a model was loading.
@st.cache_resource(show_spinner=False)
def load_dr_model(model_path):
    if not TF_AVAILABLE or not os.path.exists(model_path):
        return None
    try:
        # compile=False: the app only predicts, so the optimizer state is not needed.
        # This keeps memory within Streamlit Community Cloud's limit.
        return tf.keras.models.load_model(model_path, compile=False)
    except Exception:
        return None


# ---------------------------------------------------------
# DARK NAVY BANNER (real Streamlit widgets, approved look)
# ---------------------------------------------------------
header_box = st.container(key="header_banner") if USE_KEYED_HEADER else st.container()
column_kwargs = {"vertical_alignment": "center"} if USE_VALIGN else {}
# Old versions find the header row through this hidden marker
header_marker = "" if USE_KEYED_HEADER else '<span class="rai-header-marker"></span>'

with header_box:
    b_col1, b_col2, b_col3 = st.columns([6, 1, 1], **column_kwargs)

    with b_col1:
        st.markdown(f"""
            <div class="header-brand">{header_marker}
                <div class="eye-box">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                </div>
                <div class="brand-text">
                    <div class="title-main">RetinaAI - Diabetic Retinopathy Screening System</div>
                    <div class="title-sub">Standalone DR Image Analysis & Diagnostic Engine</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with b_col2:
        selected_model_name = st.selectbox(
            "Select Model",
            options=list(MODEL_CONFIGS.keys()),
            key="selected_model",
            label_visibility="collapsed"
        )

    with b_col3:
        if USE_BUTTON_ICON:
            st.button("New Screening", key="btn_new_screening",
                      icon=":material/refresh:", on_click=reset_screening)
        else:
            st.button("⟳  New Screening", key="btn_new_screening",
                      on_click=reset_screening)

# ---------------------------------------------------------
# MAIN TWO-COLUMN LAYOUT
# Left Column: Input Card (Top Left) + Classification Card (Bottom Left)
# Right Column: Main Grad-CAM Visualizer Container
# ---------------------------------------------------------
col_left, col_right = st.columns([5, 7], gap="large")

with col_left:
    # 1. TOP LEFT: RETINAL IMAGE INPUT CARD
    st.markdown("""
        <div class="med-card">
            <div class="card-header-row">
                <h3 class="card-title">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                        <circle cx="8.5" cy="8.5" r="1.5"></circle>
                        <polyline points="21 15 16 10 5 21"></polyline>
                    </svg>
                    RETINAL IMAGE INPUT
                </h3>
                <span class="card-subtitle-tag">PNG, JPG, TIF</span>
            </div>
            <div class="uploader-wrapper">
                <div class="custom-drop-overlay">
                    <div class="cloud-icon-circle">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="17 8 12 3 7 8"></polyline>
                            <line x1="12" y1="3" x2="12" y2="15"></line>
                        </svg>
                    </div>
                    <div class="drop-text-primary">Drag & drop fundus image here, or <span>browse</span></div>
                    <div class="drop-text-secondary">Target input resolution: 512×512 pixels</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload Fundus Image",
        type=["jpg", "jpeg", "png", "tif"],
        label_visibility="collapsed",
        key=f"uploader_{st.session_state.uploader_key}"
    )

    if uploaded_file is not None:
        raw_image = Image.open(uploaded_file).convert("RGB")
        preprocessed_rgb = ben_graham_preprocess(raw_image, target_size=(512, 512))

    # Model Inference Logic
    if uploaded_file is not None:
        model_info = MODEL_CONFIGS[selected_model_name]
        model_path = model_info["path"]
        target_layer = model_info["last_conv_layer"]
        model = load_dr_model(model_path)

        if model is None:
            # Model file missing or failed to load: show placeholder output
            predictions = [0, 0, 0, 0, 0]
            heatmap = np.zeros((16, 16))
            heatmap[5:10, 5:10] = 1.0
        else:
            img_normalized = prepare_model_input(preprocessed_rgb, model_info["input_mode"])
            img_array = np.expand_dims(img_normalized, axis=0)
            heatmap, preds = make_gradcam_heatmap(img_array, model, target_layer)
            predictions = preds.numpy()[0]
    else:
        predictions = [0, 0, 0, 0, 0]

    pred_idx = int(np.argmax(predictions))
    confidence_val = float(np.max(predictions)) * 100
    stage_name, full_title, badge_css = DR_CLASSES[pred_idx]

    stages = [
        "Grade 0: Normal / No DR",
        "Grade 1: Mild NPDR",
        "Grade 2: Moderate NPDR",
        "Grade 3: Severe NPDR",
        "Grade 4: Proliferative DR (PDR)"
    ]

    breakdown_lines = []
    for s_label, prob, bar_color in zip(stages, predictions, GRADE_BAR_COLORS):
        pct = prob * 100
        breakdown_lines.append(
            f'<div class="prob-row">'
            f'<div class="prob-header"><span>{s_label}</span><span><b>{pct:.1f}%</b></span></div>'
            f'<div class="prob-bar-bg"><div class="prob-bar-fill" style="width: {pct}%; background-color: {bar_color};"></div></div>'
            f'</div>'
        )
    breakdown_html = "".join(breakdown_lines)

    # 2. BOTTOM LEFT: CLASSIFICATION RESULT CARD
    st.markdown(f"""
<div class="med-card">
    <div class="card-header-row">
        <h3 class="card-title">CLASSIFICATION RESULT</h3>
        <div class="confidence-ring-card">
            <div class="ring-circle">{confidence_val:.1f}%</div>
            <div class="ring-label-title">CONFIDENCE SCORE</div>
        </div>
    </div>
    <div class="diag-row">
        <div>
            <div class="{badge_css}">{stage_name}</div>
            <h2 class="diag-main-title">{full_title}</h2>
        </div>
    </div>
    <div class="breakdown-label">Softmax Stage Probability Breakdown:</div>
    <div>{breakdown_html}</div>
</div>
""", unsafe_allow_html=True)

with col_right:
    # 3. SINGLE MAIN CARD: GRAD-CAM ATTENTION VISUALIZER
    main_card = card_container()

    with main_card:
        st.markdown(f"""
            <div class="card-header-row gradcam-header" style="margin-bottom: 0;">
                <div>
                    <h3 class="card-title">GRAD-CAM ATTENTION VISUALIZER ({selected_model_name.upper()})</h3>
                    <span class="card-subtitle-tag">Target Resolution: 512×512 pixels</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        g_col1, g_col2 = st.columns(2)

        with g_col1:
            with card_container():
                st.markdown('<div class="img-label-top">Uploaded Fundus Image</div>', unsafe_allow_html=True)
                if uploaded_file is not None:
                    st.markdown(image_frame_html(raw_image, "Uploaded fundus image"),
                                unsafe_allow_html=True)
                else:
                    st.markdown("""
                        <div class="img-placeholder-card">
                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="1.5">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                                <polyline points="21 15 16 10 5 21"></polyline>
                            </svg>
                            <div style="font-size: 12px; font-weight: 600; color: #94a3b8; margin-top: 8px;">No Image Loaded</div>
                            <div style="font-size: 10px; color: #64748b;">Upload a fundus image on the left</div>
                        </div>
                    """, unsafe_allow_html=True)

        with g_col2:
            with card_container():
                st.markdown('<div class="img-label-top">Grad-CAM Activation Map</div>', unsafe_allow_html=True)
                if uploaded_file is not None:
                    superimposed_gradcam = generate_superimposed_gradcam(preprocessed_rgb, heatmap, alpha=0.65)
                    st.markdown(image_frame_html(superimposed_gradcam, "Grad-CAM activation map"),
                                unsafe_allow_html=True)
                else:
                    st.markdown("""
                        <div class="img-placeholder-card">
                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="1.5">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                                <polyline points="21 15 16 10 5 21"></polyline>
                            </svg>
                            <div style="font-size: 12px; font-weight: 600; color: #94a3b8; margin-top: 8px;">Heatmap Pending</div>
                            <div style="font-size: 10px; color: #64748b;">Awaiting image input</div>
                        </div>
                    """, unsafe_allow_html=True)