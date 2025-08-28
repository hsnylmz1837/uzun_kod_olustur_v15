
import io, re, math, unicodedata
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import qrcode

st.set_page_config(page_title="Uzun Kod — v15 / Statik", page_icon="🧩", layout="wide", initial_sidebar_state="collapsed")
st.markdown('''<style>[data-testid="stSidebar"]{display:none!important;}[data-testid="collapsedControl"]{display:none!important;}
.block-container{padding-top:1.2rem;padding-bottom:2rem;}
.white-panel{background:#ffffff;color:#111827;padding:20px;border-radius:12px;box-shadow:0 2px 14px rgba(0,0,0,0.05);margin-bottom:14px;border:1px solid #e5e7eb;}
.code-panel{background:#ffffff;color:#111827;padding:20px;border-radius:12px;box-shadow:0 2px 14px rgba(0,0,0,0.05);border:1px solid #e5e7eb;}
.token{display:inline-block;background:#eef2ff;border:1px solid #c7d2fe;color:#1f2937;padding:4px 8px;border-radius:999px;margin:2px;font-size:0.85rem;}
.token.new{background:#dcfce7;border-color:#86efac;}
.smallmuted{color:#6b7280;font-size:0.85rem;}</style>''', unsafe_allow_html=True)

st.title("Uzun Kod Oluşturma Programı - v15 / Statik")
@st.cache_data
def read_schema(file):
    xls = pd.ExcelFile(file)
    dfs = {s: pd.read_excel(xls, s) for s in ["products","sections","fields","options"]}
    for col in ["PrereqFieldKey","PrereqAllowValues","SuffixKey","EncodeKey","Decimals","Widget"]:
        if col not in dfs["fields"].columns:
            dfs["fields"][col] = np.nan if col=="Decimals" else ""
    return dfs
sch = read_schema("data/schema.xlsx")

def norm(s): return str(s).strip().casefold()
def is_skip(v): return norm(v) in {"yok","diger","diğer","var"}
def sanitize(s): import re; return re.sub(r"[^A-Z0-9._-]","",str(s).upper())
def prereq_ok(fk,allow):
    fk = (fk or '').strip()
    if not fk: return True
    v = st.session_state.get("form_values",{}).get(fk)
    if v in (None,"",[]): return False
    if not allow: return True
    allowset = {a.strip() for a in str(allow).split(",") if a.strip()}
    if isinstance(v,list): return any(sanitize(x) in {sanitize(a) for a in allowset} for x in v)
    return sanitize(v) in {sanitize(a) for a in allowset}

def fmt_num(n,pad,dec):
    if pd.isna(dec): dec=0
    f=float(n)
    if int(dec)==0:
        nv=int(round(f))
        if isinstance(pad,(int,float)) and not pd.isna(pad): return f"{nv:0{int(pad)}d}"
        try:
            ps=str(pad); 
            if ps.isdigit(): return f"{nv:0{int(ps)}d}"
        except: pass
        return str(nv)
    return f"{f:.{int(dec)}f}"

if "step" not in st.session_state: st.session_state["step"]=1
if "s1" not in st.session_state: st.session_state["s1"]=None
if "s2" not in st.session_state: st.session_state["s2"]=None
if "product_row" not in st.session_state: st.session_state["product_row"]=None
if "form_values" not in st.session_state: st.session_state["form_values"]={}
if "parts" not in st.session_state: st.session_state["parts"]=[]

def big_buttons(opts, cols=3, keyp="bb"):
    cols_list=st.columns(cols); clicked=None
    for i,opt in enumerate(opts):
        with cols_list[i%cols]:
            if st.button(opt, key=f"{keyp}_{opt}", use_container_width=True): clicked=opt
    return clicked

# Step 1
if st.session_state["step"]==1:
    st.markdown('<div class="white-panel">', unsafe_allow_html=True)
    st.header("Aşama 1 — Ürün Grubu")
    s1opts = [x for x in ["Rulo Besleme","Plaka Besleme","Tamamlayıcı Ürünler"] if x in sch["products"]["Kategori1"].unique().tolist()]
    c=big_buttons(s1opts,3,"s1"); st.markdown('</div>', unsafe_allow_html=True)
    if c: st.session_state.update({"s1":c,"s2":None,"product_row":None,"form_values":{},"parts":[],"step":2}); st.rerun()

elif st.session_state["step"]==2:
    st.markdown('<div class="white-panel">', unsafe_allow_html=True)
    st.header("Aşama 2 — Alt Grup")
    sub=sch["products"].query("Kategori1 == @st.session_state['s1']")["Kategori2"].dropna().unique().tolist()
    c=big_buttons(sub,3,"s2")
    if st.button("⬅️ Geri (Aşama 1)"): st.session_state["step"]=1; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    if c: st.session_state.update({"s2":c,"product_row":None,"form_values":{},"parts":[],"step":3}); st.rerun()

else:
    s1,s2=st.session_state["s1"], st.session_state["s2"]
    st.markdown('<div class="white-panel">', unsafe_allow_html=True)
    st.header("Aşama 3 — Ürün ve Detay")
    prods=sch["products"].query("Kategori1==@s1 and Kategori2==@s2")
    display=prods["UrunAdi"]+" — "+prods["MakineTipi"]
    ch=st.selectbox("Ürün", options=display.tolist(), placeholder="Seçiniz")
    if ch: st.session_state["product_row"]=prods.iloc[display.tolist().index(ch)]
    row=st.session_state["product_row"]
    if row is not None:
        st.info(f"Seçilen: **{row['MakineTipi']}**")
        secs=sch["sections"].query("Kategori1==@s1 and Kategori2==@s2 and MakineTipi==@row['MakineTipi']").sort_values("Order")
        tabs=st.tabs([sec["SectionLabel"] for _,sec in secs.iterrows()])
        for i,(_,sec) in enumerate(secs.iterrows()):
            with tabs[i]:
                fdf=sch["fields"].query("SectionKey == @sec['SectionKey']")
                for _,fld in fdf.iterrows():
                    k=fld["FieldKey"]; typ=str(fld["Type"]).lower(); req=bool(fld["Required"])
                    en=prereq_ok(fld.get("PrereqFieldKey"), fld.get("PrereqAllowValues"))
                    if typ in ("select","multiselect"):
                        opts=sch["options"].query("OptionsKey == @fld['OptionsKey']").sort_values("Order")
                        codes=opts["ValueCode"].astype(str).tolist()
                        labels=(opts["ValueCode"].astype(str)+" — "+opts["ValueLabel"].astype(str)).tolist()
                        if typ=="select":
                            sel=st.selectbox(fld["FieldLabel"]+(" *" if req else ""), options=codes, format_func=lambda c: labels[codes.index(c)], index=None, disabled=not en, placeholder="Seçiniz", key="k_"+k)
                            if en and sel is not None: st.session_state["form_values"][k]=sel
                            else: st.session_state["form_values"].pop(k, None)
                        else:
                            ms=st.multiselect(fld["FieldLabel"]+(" *" if req else ""), options=codes, format_func=lambda c: labels[codes.index(c)], default=[], disabled=not en, key="k_"+k)
                            if en and ms: st.session_state["form_values"][k]=ms
                            else: st.session_state["form_values"].pop(k, None)
                    elif typ=="number":
                        d=int(fld.get("Decimals") if not pd.isna(fld.get("Decimals")) else 0)
                        step = 1 if d==0 else 10**(-d)
                        if not pd.isna(fld.get("Step")): step = float(fld.get("Step"))
                        if d==0:
                            v=st.number_input(fld["FieldLabel"]+(" *" if req else ""), min_value=int(fld["Min"]) if not pd.isna(fld["Min"]) else None, max_value=int(fld["Max"]) if not pd.isna(fld["Max"]) else None, value=int(fld["Default"]) if not pd.isna(fld["Default"]) else 0, step=int(step), format="%d", disabled=not en, key="k_"+k)
                        else:
                            fmt=f"%.{d}f"
                            v=st.number_input(fld["FieldLabel"]+(" *" if req else ""), min_value=float(fld["Min"]) if not pd.isna(fld["Min"]) else None, max_value=float(fld["Max"]) if not pd.isna(fld["Max"]) else None, value=float(fld["Default"]) if not pd.isna(fld["Default"]) else 0.0, step=float(step), format=fmt, disabled=not en, key="k_"+k)
                        if en: st.session_state["form_values"][k]=v
                    else:
                        t=st.text_input(fld["FieldLabel"]+(" *" if req else ""), value=str(fld.get("Default") or ""), disabled=not en, key="k_"+k, placeholder="Seçiniz")
                        if en and t.strip(): st.session_state["form_values"][k]=t
                        else: st.session_state["form_values"].pop(k, None)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="code-panel">', unsafe_allow_html=True)
    def rebuild_parts():
        parts=[]; row=st.session_state.get("product_row")
        if row is None: return parts
        m=sanitize(row["MakineTipi"]); 
        if m: parts.append(m)
        secs=sch["sections"].query("Kategori1==@s1 and Kategori2==@s2 and MakineTipi==@row['MakineTipi']").sort_values("Order")
        for _,sec in secs.iterrows():
            fdf=sch["fields"].query("SectionKey == @sec['SectionKey']")
            for _,fld in fdf.iterrows():
                k=fld["FieldKey"]; typ=str(fld["Type"]).lower(); val=st.session_state.get("form_values",{}).get(k)
                if val in (None,"",[],0): continue
                if typ=="select":
                    if is_skip(val): continue
                    parts.append(sanitize(val))
                elif typ=="multiselect" and isinstance(val,list):
                    subset=sch["options"].query("OptionsKey == @fld['OptionsKey']")
                    order={str(r["ValueCode"]): int(r["Order"]) for _,r in subset.iterrows()}
                    clean=[v for v in val if not is_skip(v)]
                    ordered=sorted(clean, key=lambda v: order.get(str(v),999999))
                    if ordered: parts.append("".join([sanitize(v) for v in ordered]))
                elif typ=="number":
                    num = fmt_num(val, fld.get("Pad"), fld.get("Decimals"))
                    pre=str(fld.get("EncodeKey") or ""); suf=str(fld.get("SuffixKey") or "")
                    parts.append(f"{pre}{num}{suf}" if (pre or suf) else num)
                else:
                    txt=str(val); pre=str(fld.get("EncodeKey") or ""); suf=str(fld.get("SuffixKey") or "")
                    piece=f"{pre}{txt}{suf}" if (pre or suf) else txt
                    if piece.strip(): parts.append(piece)
        return parts
    new_parts = rebuild_parts()
    st.session_state["parts"]=new_parts
    code=" ".join(new_parts)
    st.code(code or "Kod için seçim yapın…", language="text")
    st.download_button("Kodu TXT indir", data=code.encode("utf-8"), file_name="uzun_kod.txt")
    st.markdown('</div>', unsafe_allow_html=True)
