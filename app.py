"""Yerelde çalışan çoklu görsel ve belge maskeleme demosu."""

from hashlib import sha256
from io import BytesIO
import time
from urllib.request import urlopen

import pandas as pd
import streamlit as st
from PIL import Image

from core import load_image, mask_regions, preview_boxes
from detectors import Region, detect_image
from documents import analyze_pdf, export_redacted_pdf
from video import inspect_video, process_video
from prompt_guard import analyze_prompt, get_rules, mask_prompt, save_rules


st.set_page_config(page_title="OneTech Studio | Veri Maskeleme", page_icon="🛡️", layout="wide")
public_demo = not st.context.url.startswith(("http://localhost", "http://127.0.0.1"))
st.markdown("""
<style>
:root {--surface:#111c2d;--line:#263a51;--accent:#62d6c4;}
.stApp {background: radial-gradient(circle at 80% -10%,#18344a 0,transparent 38%),#08131f;color:#edf5f5;}
.block-container {max-width: 1420px; padding-top: 1.3rem; padding-bottom: 4rem;}
[data-testid="stSidebar"] {background:#0d1b2a;border-right:1px solid var(--line);}
button[data-testid="stBaseButton-header"] {display:none;}
[data-testid="stMetric"] {background:var(--surface);border:1px solid var(--line);padding:14px;border-radius:14px;}
[data-testid="stMetricLabel"] {color:#9fb6c6;}
div[data-testid="stDownloadButton"] button {width:100%;}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {background:#52c7b7;color:#071820;border:0;font-weight:700;}
.stTabs [data-baseweb="tab-list"] {gap:12px;border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"] {padding:12px 18px;border-radius:10px 10px 0 0;color:#aec1cc;}
.stTabs [aria-selected="true"] {background:#14283a;color:#77e3d1;}
.hero {border:1px solid #305769;background:linear-gradient(110deg,#102b3c 0%,#102134 58%,#151f36 100%);border-radius:20px;padding:28px 34px;margin:0 0 22px;box-shadow:0 12px 38px #0002;}
.eyebrow {color:#72dccb;font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;margin-bottom:10px;}
.hero h1 {font-size:clamp(27px,3vw,42px);line-height:1.12;margin:0 0 12px;color:#f3fbfa;font-weight:800;}
.hero p {font-size:15px;color:#bfd0da;margin:0;max-width:920px;line-height:1.55;}
.hero-tags {display:flex;gap:8px;flex-wrap:wrap;margin-top:18px;}
.hero-tags span {border:1px solid #356476;background:#173848;color:#bceee5;border-radius:20px;padding:5px 11px;font-size:12px;font-weight:700;}
.section-note {color:#9db3c2;font-size:13px;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="eyebrow">OneTech Studio · veri maskeleme çalışma alanı</div>
  <h1>Hassas veriyi gör. Kontrol et. Maskele.</h1>
  <p>AI sitelerine giden istemler, fotoğraflar, PDF belgeler ve kısa videolar için tek bir stüdyo.
  Otomatik adayları incele, maskeyi düzenle ve sonucu indir.</p>
  <div class="hero-tags"><span>✦ Prompt koruması</span><span>◉ Yüz &amp; plaka</span>
  <span>▤ Belge &amp; PDF</span><span>▶ Video</span></div>
</div>
""", unsafe_allow_html=True)
if public_demo:
    st.warning("Çevrimiçi demo: girdiğiniz metin ve yüklediğiniz dosyalar bu uygulamanın sunucusunda işlenir. "
               "Gerçek kişisel veya gizli veri yüklemeyin; sentetik örnek kullanın. "
               "Tarayıcı eklentisi yalnızca kendi bilgisayarınızda çalışan yerel API ile çalışır.")

with st.sidebar:
    st.title("◈ OneTech Studio")
    st.caption("Maskeleme çalışma alanı")
    st.divider()
    st.subheader("Görsel analiz ayarları")
    selected_types = st.multiselect("Otomatik bulunacak alanlar", ["Yüz", "Plaka", "Hassas metin"],
                                    default=["Yüz", "Plaka", "Hassas metin"])
    faces = "Yüz" in selected_types
    plates = "Plaka" in selected_types
    text = "Hassas metin" in selected_types
    threshold = st.slider("AI güven eşiği", 0.30, 0.85, 0.45, 0.05)
    method_label = st.selectbox("Fotoğraf / video maskesi", ["Harita tarzı yoğun blur", "Siyah kapatma", "Pikselleştirme"])
    method = {"Siyah kapatma": "black", "Harita tarzı yoğun blur": "blur",
              "Pikselleştirme": "pixel"}[method_label]
    if method != "black":
        st.caption("Blur görsel demoda iyi görünür. Kesin gizleme gereken dosyalarda siyah kapatma seçin.")
    st.divider()
    st.caption("AI modelleri aday alan bulur. Çıktıyı indirmeden önce bütün hassas bölgeleri gözle kontrol edin.")


@st.cache_data(show_spinner="Fotoğraf analiz ediliyor…")
def analyze_photo(data: bytes, faces: bool, plates: bool, text: bool, threshold: float):
    started = time.perf_counter()
    image = load_image(BytesIO(data))
    regions = detect_image(image, faces, plates, text, threshold)
    return image, regions, round(time.perf_counter() - started, 2)


@st.cache_data(show_spinner="PDF sayfaları analiz ediliyor…")
def analyze_document(data: bytes, faces: bool, plates: bool, text: bool, threshold: float):
    started = time.perf_counter()
    pages = analyze_pdf(data, faces, plates, text, threshold)
    return pages, round(time.perf_counter() - started, 2)


@st.cache_data(show_spinner="Video bilgileri okunuyor…")
def video_preview(data: bytes, suffix: str):
    return inspect_video(data, suffix)


TABLE_COLUMNS = ["Kapat", "Tür", "Kaynak", "Güven", "x1", "y1", "x2", "y2"]


def _table_key(file_id: str, part: str) -> str:
    options = f"{faces}{plates}{text}{threshold}"
    return f"tablo_{file_id}_{part}_{options}"


def _default_table(regions: list[Region]) -> pd.DataFrame:
    return pd.DataFrame([region.row() for region in regions], columns=TABLE_COLUMNS)


def _boxes(table: pd.DataFrame, width: int, height: int):
    boxes = []
    for _, row in table.iterrows():
        if not bool(row.get("Kapat", False)):
            continue
        try:
            x1, y1, x2, y2 = (int(row[k]) for k in ("x1", "y1", "x2", "y2"))
        except (TypeError, ValueError):
            continue
        x1, x2 = sorted((max(0, min(width, x1)), max(0, min(width, x2))))
        y1, y2 = sorted((max(0, min(height, y1)), max(0, min(height, y2))))
        if x2 > x1 and y2 > y1:
            boxes.append((x1, y1, x2, y2))
    return boxes


def region_editor(file_id: str, part: str, image, regions: list[Region]):
    height, width = image.shape[:2]
    key = _table_key(file_id, part)
    if key not in st.session_state:
        st.session_state[key] = _default_table(regions)
    st.caption("Adayları kapat/aç, koordinatları düzelt veya tablonun altından elle yeni satır ekle. "
               f"Koordinatlar {width} × {height} piksellik önizlemeye göredir.")
    edited = st.data_editor(
        st.session_state[key], key=f"editor_{key}", num_rows="dynamic", hide_index=True,
        width="stretch",
        column_config={
            "Kapat": st.column_config.CheckboxColumn("Kapat", default=True),
            "Tür": st.column_config.TextColumn("Tür", help="Elle eklenen alan için bir ad yazabilirsiniz."),
            "Kaynak": st.column_config.TextColumn("Kaynak"),
            "Güven": st.column_config.NumberColumn("Güven", format="%.2f"),
            "x1": st.column_config.NumberColumn("Sol x", min_value=0, max_value=width),
            "y1": st.column_config.NumberColumn("Üst y", min_value=0, max_value=height),
            "x2": st.column_config.NumberColumn("Sağ x", min_value=0, max_value=width),
            "y2": st.column_config.NumberColumn("Alt y", min_value=0, max_value=height),
        },
    )
    st.session_state[key] = edited
    return _boxes(edited, width, height)


def show_comparison(image, boxes, method: str):
    left, right = st.columns(2)
    with left:
        st.subheader("Önce · seçili kutular")
        st.image(preview_boxes(image, boxes), width="stretch")
    with right:
        st.subheader("Sonra · maskelenmiş")
        masked = mask_regions(image, boxes, method)
        st.image(masked, width="stretch")
    return masked


prompt_tab, photo_tab, pdf_tab, video_tab, about_tab = st.tabs(
    ["✦ Prompt koruması", "📷 Fotoğraf", "📄 PDF / belge", "🎬 Video", "ℹ️ Kapsam"])

with prompt_tab:
    st.subheader("AI istemini göndermeden önce denetle")
    st.caption("Çevrimiçi demoda kurallar bu tarayıcı oturumuna özeldir. "
               "Eklentiyle ortak kurallar için projeyi kendi bilgisayarınızda çalıştırın."
               if public_demo else
               "OneTech Chrome eklentisi bu ekrandaki kuralları kullanır. İstem yalnızca bu bilgisayardaki servise gönderilir.")
    rules = st.session_state.setdefault("prompt_rules", []) if public_demo else get_rules()
    left, right = st.columns([1.1, .9], gap="large")
    with left:
        sample = "Müşteri e-postası: ayse.ornek@example.com\nTelefon: 0532 123 45 67\nBu verileri özetle."
        prompt = st.text_area("İncelenecek istem", value=sample, height=190, key="prompt_text")
        if st.button("İstemi incele", type="primary", disabled=not prompt.strip()):
            try:
                st.session_state["prompt_result"] = analyze_prompt(prompt, rules=rules)
            except ValueError as error:
                st.error(str(error))
        result = st.session_state.get("prompt_result")
        if result and result["originalPrompt"] != prompt:
            result = None
        if result:
            matches = result["matches"]
            if matches:
                st.success(f"{len(matches)} hassas alan adayı bulundu. Gönderilecek alanları kontrol edin.")
                rows = pd.DataFrame([{"Maskele": True, "Tür": item["type"], "Bulunan": item["original"]}
                                     for item in matches])
                match_key = sha256(repr(matches).encode("utf-8")).hexdigest()[:16]
                edited = st.data_editor(rows, hide_index=True, width="stretch", key=f"prompt_matches_{match_key}",
                                        column_config={"Maskele": st.column_config.CheckboxColumn("Maskele")},
                                        disabled=["Tür", "Bulunan"])
                enabled = edited["Maskele"].fillna(False).tolist()
                protected = mask_prompt(prompt, matches, enabled)
                st.markdown("**Gönderilecek metin**")
                st.code(protected, language=None, wrap_lines=True)
                st.download_button("Maskelenmiş metni indir", protected.encode("utf-8"),
                                   file_name="maskelenmis_istem.txt", mime="text/plain")
                if not all(enabled):
                    st.warning("Bazı alanların maskesi kapatıldı; gönderilecek metni yeniden inceleyin.")
            else:
                st.info("Bu kurallara göre hassas alan bulunmadı. Sonucu yine de okuyarak kontrol edin.")
    with right:
        st.markdown("**Eklenti bağlantısı**")
        if public_demo:
            st.info("Eklenti, GitHub'daki `extension/` klasöründen yüklenir ve kendi bilgisayarınızdaki "
                    "`prompt_api.py` servisine bağlanır. Çevrimiçi demo eklentinin yerel servisi değildir.")
        else:
            try:
                with urlopen("http://127.0.0.1:8765/api/health", timeout=.3) as response:
                    service_ready = response.status == 200
            except OSError:
                service_ready = False
            if service_ready:
                st.success("Yerel prompt servisi çalışıyor · 127.0.0.1:8765")
            else:
                st.warning("Yerel prompt servisi kapalı. Eklentinin çalışması için başlatma betiğini açın.")
        st.markdown("Chrome'da `extension/` klasörünü **Paketlenmemiş öğe yükle** ile ekleyin. "
                    "ChatGPT, Gemini veya Claude sayfasında metin gönderirken önce OneTech önizlemesi açılır.")
        with st.expander("Özel kelime ve kurum kuralları"):
            st.caption("Eklediğiniz ifadeler istemde bulunduğunda [OZEL-KURAL] ile değiştirilir. "
                       + ("Kurallar yalnızca bu oturumda tutulur." if public_demo else "Kurallar bu bilgisayarda saklanır."))
            new_rule = st.text_input("Yeni ifade", max_chars=100, key="new_prompt_rule")
            if st.button("Kural ekle", disabled=not new_rule.strip()):
                try:
                    if public_demo:
                        st.session_state["prompt_rules"] = list(dict.fromkeys(rules + [new_rule]))[:50]
                    else:
                        save_rules(rules + [new_rule])
                    st.session_state.pop("prompt_result", None)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
            if rules:
                to_remove = st.selectbox("Silinecek kural", rules)
                if st.button("Seçili kuralı sil"):
                    if public_demo:
                        st.session_state["prompt_rules"] = [rule for rule in rules if rule != to_remove]
                    else:
                        save_rules([rule for rule in rules if rule != to_remove])
                    st.session_state.pop("prompt_result", None)
                    st.rerun()
                st.caption(f"{len(rules)} kayıtlı özel kural")

with photo_tab:
    st.subheader("Fotoğrafta birden fazla alanı maskele")
    photo = st.file_uploader("JPG veya PNG yükle", type=["jpg", "jpeg", "png"],
                             max_upload_size=10, key="photo_file")
    if photo:
        data = photo.getvalue()
        file_id = sha256(data).hexdigest()[:16]
        try:
            image, regions, elapsed = analyze_photo(data, faces, plates, text, threshold)
        except Exception as error:
            st.error(f"Fotoğraf işlenemedi: {error}")
        else:
            a, b, c = st.columns(3)
            a.metric("Aday bölge", len(regions))
            b.metric("Analiz süresi", f"{elapsed} sn")
            c.metric("Görüntü", f"{image.shape[1]} × {image.shape[0]}")
            if not regions:
                st.info("Otomatik aday bulunamadı. Eşiği düşürün veya tabloya elle bölge ekleyin.")
            boxes = region_editor(file_id, "foto", image, regions)
            masked = show_comparison(image, boxes, method)
            if not boxes:
                st.warning("Seçili maske yok. Çıktı indirmek için en az bir bölge seçin veya ekleyin.")
            buffer = BytesIO()
            Image.fromarray(masked).save(buffer, format="PNG")
            st.download_button("Maskelenmiş PNG indir", buffer.getvalue(),
                               file_name="maskelenmis_fotograf.png", mime="image/png", type="primary",
                               disabled=not boxes)

with pdf_tab:
    st.subheader("PDF'deki hassas bilgileri kapat")
    st.caption("Metin katmanını okur; taranmış sayfalarda OCR kullanır. Çıktı, yeni görüntü tabanlı PDF'dir.")
    pdf = st.file_uploader("PDF yükle (en fazla 8 sayfa)", type=["pdf"],
                           max_upload_size=12, key="pdf_file")
    if pdf:
        data = pdf.getvalue()
        file_id = sha256(data).hexdigest()[:16]
        try:
            pages, elapsed = analyze_document(data, faces, plates, text, threshold)
        except Exception as error:
            st.error(f"PDF işlenemedi: {error}")
        else:
            a, b, c = st.columns(3)
            a.metric("Sayfa", len(pages))
            b.metric("Aday bölge", sum(len(page.regions) for page in pages))
            c.metric("Analiz süresi", f"{elapsed} sn")
            page_index = st.selectbox("İncelenecek sayfa", range(len(pages)),
                                      format_func=lambda i: f"Sayfa {i + 1}")
            current = pages[page_index]
            st.caption(f"Metin kaynağı: {current.text_source}")
            boxes = region_editor(file_id, f"pdf_{page_index}", current.image, current.regions)
            show_comparison(current.image, boxes, "black")
            all_boxes = []
            for index, page in enumerate(pages):
                key = _table_key(file_id, f"pdf_{index}")
                table = st.session_state.get(key, _default_table(page.regions))
                all_boxes.append(_boxes(table, page.image.shape[1], page.image.shape[0]))
            result = export_redacted_pdf(pages, all_boxes)
            if not any(all_boxes):
                st.warning("Hiç maske seçili değil. Çıktı indirmek için en az bir bölge seçin veya ekleyin.")
            st.download_button("Maskelenmiş PDF indir", result, file_name="maskelenmis_belge.pdf",
                               mime="application/pdf", type="primary", disabled=not any(all_boxes))
            st.info("PDF yeniden oluşturulduğu için orijinal metin katmanı ve metadata çıktıya taşınmaz. "
                    "Metin seçme/arama özelliği de kaybolur.")

with video_tab:
    st.subheader("Kısa videoda yüz ve plakaları maskele")
    st.caption("İlk 12 saniye, en fazla 8 FPS ve 960 piksel genişlik; ses çıktıya alınmaz. "
               "Algılayıcı bir karede alan kaçırırsa kısa süreli takip kullanılabilir.")
    video = st.file_uploader("MP4, MOV veya AVI yükle", type=["mp4", "mov", "avi"],
                             max_upload_size=30, key="video_file")
    if video:
        data = video.getvalue()
        file_id = sha256(data).hexdigest()[:16]
        suffix = "." + video.name.rsplit(".", 1)[-1].lower()
        try:
            info = video_preview(data, suffix)
        except Exception as error:
            st.error(f"Video okunamadı: {error}")
        else:
            st.image(info.preview, caption=f"İlk kare · {info.width} × {info.height} · {info.fps:.1f} FPS",
                     width="stretch")
            if info.duration > 0:
                st.caption(f"Kaynak süre: {info.duration:.1f} sn · işlenecek bölüm: ilk {min(info.duration, 12):.1f} sn")
            manual = None
            temporal = st.checkbox("Kaçırılan karelerde kısa süreli yüz/plaka takibi", value=True,
                                   help="Her karede algılama sürer. Takip yalnızca kısa süreli eksikleri tamamlar.")
            with st.expander("Videonun tüm karelerine sabit manuel kutu ekle"):
                enabled = st.checkbox("Sabit bölge kullan", key="video_manual")
                if enabled:
                    x1 = st.number_input("Sol x", 0, info.width - 1, 0)
                    y1 = st.number_input("Üst y", 0, info.height - 1, 0)
                    x2 = st.number_input("Sağ x", 1, info.width, min(100, info.width))
                    y2 = st.number_input("Alt y", 1, info.height, min(100, info.height))
                    manual = (x1, y1, x2, y2)
            result_key = f"video_result_{file_id}_{faces}_{plates}_{threshold}_{method}_{manual}_{temporal}"
            if st.button("Videoyu işle", type="primary"):
                try:
                    with st.spinner("Kareler algılanıyor ve MP4 üretiliyor…"):
                        st.session_state[result_key] = process_video(
                            data, suffix, faces, plates, threshold, method, manual, temporal)
                except Exception as error:
                    st.error(f"Video işlenemedi: {error}")
            if result_key in st.session_state:
                result, stats = st.session_state[result_key]
                st.success(f"{stats['kare']} kare işlendi · {stats['algılama']} otomatik aday · "
                           f"{stats['takiple_eklenen']} takip kutusu · {stats['süre']} sn işlem süresi")
                if stats["maskesiz_kare"]:
                    st.warning(f"{stats['maskesiz_kare']} karede yüz/plaka maskesi bulunmadı. "
                               "Çıktıyı kare kare gözden geçirin; gerekiyorsa sabit kutu ekleyin.")
                    with st.expander("Maskesiz karelerin zamanları"):
                        times = stats.get("maskesiz_zamanlar", [])
                        st.write(", ".join(f"{value:.2f} sn" for value in times))
                if stats["algılama"] == 0 and manual is None:
                    st.warning("Bu videoda otomatik alan bulunmadı; çıktı maskesiz olabilir. "
                               "Sabit manuel kutu ekleyip tekrar işleyin.")
                st.video(result)
                st.download_button("Maskelenmiş MP4 indir", result, file_name="maskelenmis_video.mp4",
                                   mime="video/mp4", disabled=stats["algılama"] == 0 and manual is None)

with about_tab:
    st.markdown("""
### Bu demoda çalışanlar
- **Prompt:** OneTech Chrome eklentisi; ortak yerel metin kuralları, özel ifadeler ve gönderim öncesi seçim.
- **AI:** OpenCV YuNet yüz tespiti ve YOLOv9 plaka tespiti.
- **Belge:** RapidOCR Latin modelinin bulduğu satırlar veya PDF metin katmanı; e-posta, telefon,
  doğrulanmış T.C. kimlik no, IBAN ve ad/adres/belge numarası etiketleri için kurallar.
- **Kontrol:** Aday kutu seçimi, koordinat düzeltme, elle satır ekleme, önce/sonra önizleme.
- **Çıktı:** Fotoğrafta PNG, belgede yeniden oluşturulmuş PDF, kısa videoda MP4.
- **Görünüm:** Fotoğraf ve videoda varsayılan yoğun blur; PDF'de siyah kapatma.

### Hâlâ deney aşamasında
Etiketsiz kişi adı ve imza otomatik tespiti, canlı kamera ve plaka modelinin Türk plakaları
üzerindeki ölçülmüş başarımı sonraki aşamalardır. OCR ve dedektörler alan kaçırabilir;
çıktıyı gözle kontrol etmek gerekir. Gerçek kişisel veriler yerine sentetik test dosyaları kullanın.
""")
