"""Tarayıcıdan kullanılabilen JSON API'si (yalnızca standart kütüphane).

Başlatma: ``python3 -m harcama_takip.web --port 8000 [--db yol]``

Uç noktalar:
    GET    /api/harcamalar[?ay=YYYY-AA&kategori=...]  liste
    POST   /api/harcamalar                            ekle (JSON gövde)
    DELETE /api/harcamalar/<id>                       sil
    GET    /api/rapor?ay=YYYY-AA                      aylık kategori raporu
    GET    /export.csv[?ay=YYYY-AA&kategori=...]      CSV dışa aktarma

Tutarlar JSON'da ``tutar_kurus`` (tam sayı) ve ``tutar`` (Türkçe metin) olarak
döner; rapor yüzdeleri ``Decimal`` metnidir. API'de float kullanılmaz.
Her istek kendi Veritabani bağlantısını açıp kapatır.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import traceback
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlsplit

from harcama_takip.cli import csv_akisa_yaz
from harcama_takip.rapor import AylikRapor, aylik_rapor
from harcama_takip.veri import (
    Harcama,
    HarcamaBulunamadi,
    HarcamaHatasi,
    Veritabani,
    kurus_metni,
)

VARSAYILAN_HOST = "127.0.0.1"
VARSAYILAN_PORT = 8000
EN_BUYUK_GOVDE = 64 * 1024  # bayt

SAYFA_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Harcama Takip</title>
<style>
:root{--bg:#f6f7f9;--kart:#fff;--yazi:#1c1e21;--soluk:#667085;--cizgi:#d9dde3;--vurgu:#2563eb;--vurgu-koyu:#1d4ed8;--uzerine:#fff;--tehlike:#c62828;--ok:#15803d;--hata-bg:#fdecec;--zebra:#f4f6fa;--hover:#e6eeff;--bas:#7c3aed;--son:#2563eb}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--kart:#1e2127;--yazi:#e8eaed;--soluk:#9aa3b2;--cizgi:#343a45;--vurgu:#6ea0ff;--vurgu-koyu:#8fb6ff;--uzerine:#0b1020;--tehlike:#ef6b6b;--ok:#22a06b;--hata-bg:#3a1f22;--zebra:#191c22;--hover:#263047;--bas:#7c3aed;--son:#2563eb}}
html[data-tema="koyu"]{--bg:#14161a;--kart:#1e2127;--yazi:#e8eaed;--soluk:#9aa3b2;--cizgi:#343a45;--vurgu:#6ea0ff;--vurgu-koyu:#8fb6ff;--uzerine:#0b1020;--tehlike:#ef6b6b;--ok:#22a06b;--hata-bg:#3a1f22;--zebra:#191c22;--hover:#263047;--bas:#7c3aed;--son:#2563eb}
html[data-tema="açık"]{--bg:#f6f7f9;--kart:#fff;--yazi:#1c1e21;--soluk:#667085;--cizgi:#d9dde3;--vurgu:#2563eb;--vurgu-koyu:#1d4ed8;--uzerine:#fff;--tehlike:#c62828;--ok:#15803d;--hata-bg:#fdecec;--zebra:#f4f6fa;--hover:#e6eeff;--bas:#7c3aed;--son:#2563eb}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--yazi)}
header.ust{background:linear-gradient(135deg,var(--bas),var(--son));color:#fff;box-shadow:0 2px 10px rgba(0,0,0,.2)}
.ust-ic{max-width:960px;margin:0 auto;padding:16px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.ust h1{font-size:1.5rem;margin:0;color:#fff}
.alt{margin:2px 0 0;font-size:.9rem;opacity:.9}
header.ust button.ikincil{background:rgba(255,255,255,.15);color:#fff;border-color:#fff}
header.ust button.ikincil:hover{background:rgba(255,255,255,.28);color:#fff;border-color:#fff}
main{max-width:960px;margin:0 auto;padding:12px 16px}
.ozet{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:12px 0 16px}
.ozet-kart{color:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 4px 14px rgba(0,0,0,.12)}
.ozet-kart .etiket{font-size:.8rem;opacity:.9;text-transform:uppercase;letter-spacing:.04em}
.ozet-kart .deger{font-size:1.4rem;font-weight:700;margin-top:4px;word-break:break-word}
.o-mavi{background:linear-gradient(135deg,#2563eb,#1d4ed8)}
.o-yesil{background:linear-gradient(135deg,#16a34a,#15803d)}
.o-turuncu{background:linear-gradient(135deg,#ea580c,#c2410c)}
section{background:var(--kart);border:1px solid var(--cizgi);border-top:4px solid var(--vurgu);border-radius:12px;padding:14px;margin-bottom:16px;box-shadow:0 2px 10px rgba(0,0,0,.06)}
section.tablo-kart{border-top-color:var(--ok)}
section.rapor-kart{border-top-color:#b45309}
h2{font-size:1.1rem;margin:0 0 10px;display:flex;align-items:center;gap:8px}
h2::before{content:"";width:10px;height:10px;border-radius:50%;background:var(--vurgu);flex:none}
section.tablo-kart h2::before{background:var(--ok)}
section.rapor-kart h2::before{background:#b45309}
form,.filtre{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;align-items:end}
label{display:flex;flex-direction:column;font-size:.85rem;color:var(--soluk);gap:3px;font-weight:500}
input,button,a.dugme{font:inherit;padding:8px;border-radius:8px;border:1px solid var(--cizgi);background:var(--bg);color:var(--yazi)}
input:focus{outline:none;border-color:var(--vurgu);box-shadow:0 0 0 3px rgba(37,99,235,.25)}
button{background:var(--vurgu);color:var(--uzerine);border-color:var(--vurgu);cursor:pointer;font-weight:600;transition:background .15s,color .15s}
button:hover{background:var(--vurgu-koyu);border-color:var(--vurgu-koyu)}
button:focus-visible,a.dugme:focus-visible,input:focus-visible{outline:3px solid var(--vurgu);outline-offset:2px}
button.ikincil{background:transparent;color:var(--vurgu)}
button.ikincil:hover{background:var(--hover);color:var(--vurgu);border-color:var(--vurgu)}
button.sil{background:transparent;color:var(--tehlike);border-color:var(--tehlike);padding:4px 8px}
button.sil:hover{background:var(--tehlike);color:#fff;border-color:var(--tehlike)}
a.dugme{display:inline-flex;align-items:center;justify-content:center;padding:8px 12px;border:1px solid var(--vurgu);color:var(--vurgu);text-decoration:none;font-weight:600;background:transparent}
a.dugme:hover{background:var(--hover)}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--cizgi);font-size:.92rem;vertical-align:middle}
th{color:var(--soluk);font-weight:600;font-size:.8rem;text-transform:uppercase;letter-spacing:.03em}
td.sayi,th.sayi{text-align:right}
td.tutar{font-weight:700;font-variant-numeric:tabular-nums}
tbody tr:nth-child(even){background:var(--zebra)}
tbody tr:hover{background:var(--hover)}
.tablo{overflow-x:auto}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;color:#fff;font-size:.8rem;font-weight:600;white-space:nowrap}
.cubuk{height:6px;background:var(--cizgi);border-radius:4px;margin-top:6px;overflow:hidden;min-width:80px}
.cubuk span{display:block;height:100%;border-radius:4px}
#mesaj{margin:0 0 8px;color:var(--tehlike);background:var(--hata-bg);border:1px solid var(--tehlike);border-radius:8px;padding:8px 12px}
#mesaj:empty{display:none}
.toast{position:fixed;left:50%;bottom:20px;transform:translate(-50%,16px);background:var(--ok);color:#fff;padding:10px 18px;border-radius:999px;box-shadow:0 6px 18px rgba(0,0,0,.25);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;font-weight:600}
.toast.gorunur{opacity:1;transform:translate(-50%,0)}
.bos{color:var(--soluk)}
a{color:var(--vurgu)}
@media (max-width:600px){.ozet,form,.filtre{grid-template-columns:1fr}.ust-ic{flex-direction:column;align-items:flex-start}}
</style>
</head>
<body>
<header class="ust">
<div class="ust-ic">
<div><h1>Harcama Takip</h1><p class="alt">Harcamalarını kaydet, kategorilere göre izle</p></div>
<button type="button" id="tema" class="ikincil">Tema: otomatik</button>
</div>
</header>
<main>
<div class="ozet" aria-label="Özet">
<div class="ozet-kart o-mavi"><div class="etiket">Aylık toplam (<span id="ozet-ay">—</span>)</div><div class="deger" id="ozet-toplam">—</div></div>
<div class="ozet-kart o-yesil"><div class="etiket">Kayıt sayısı</div><div class="deger" id="ozet-adet">—</div></div>
<div class="ozet-kart o-turuncu"><div class="etiket">En çok harcanan kategori</div><div class="deger" id="ozet-kategori">—</div></div>
</div>
<p id="mesaj" role="alert"></p>
<div id="bildirim" class="toast" role="status"></div>
<section>
<h2>Yeni harcama</h2>
<form id="ekle-formu">
<label>Tutar (TL)<input name="tutar" required inputmode="decimal" placeholder="150.50"></label>
<label>Kategori<input name="kategori" required placeholder="market"></label>
<label>Tarih<input name="tarih" type="date"></label>
<label>Açıklama<input name="aciklama" placeholder="isteğe bağlı"></label>
<button type="submit">Ekle</button>
</form>
</section>
<section class="tablo-kart">
<h2>Harcamalar</h2>
<div class="filtre">
<label>Ay<input id="f-ay" type="month"></label>
<label>Kategori<input id="f-kategori" placeholder="tümü"></label>
<button type="button" id="filtrele">Filtrele</button>
<a id="csv" class="dugme" href="/export.csv" download="harcamalar.csv">CSV dışa aktar</a>
</div>
<div class="tablo">
<table>
<thead><tr><th>Tarih</th><th>Kategori</th><th>Açıklama</th><th class="sayi">Tutar</th><th></th></tr></thead>
<tbody id="liste"></tbody>
</table>
</div>
</section>
<section class="rapor-kart">
<h2>Aylık rapor</h2>
<p class="bos" id="rapor-ozet">Rapor için yukarıdan bir ay seçin.</p>
<div class="tablo">
<table>
<thead><tr><th>Kategori</th><th class="sayi">Tutar</th><th class="sayi">Yüzde</th></tr></thead>
<tbody id="rapor"></tbody>
</table>
</div>
</section>
</main>
<script>
(function(){
"use strict";
var $=function(id){return document.getElementById(id);};
function mesaj(m){$("mesaj").textContent=m||"";}
function hucre(tr,metin,sinif){var td=document.createElement("td");td.textContent=metin;if(sinif)td.className=sinif;tr.appendChild(td);return td;}
async function istek(url,secenek){
  var y=await fetch(url,secenek);var v=await y.json();
  if(!y.ok)throw new Error(v.hata||"İstek başarısız.");
  return v;
}
var PALET=["#2563eb","#15803d","#b45309","#7e22ce","#be185d","#0e7490","#4d7c0f","#c2410c"];
function kategoriRenk(ad){var h=0;for(var i=0;i<ad.length;i++){h=(h*31+ad.charCodeAt(i))>>>0;}return PALET[h%PALET.length];}
function kategoriHucre(tr,ad){var td=document.createElement("td");var s=document.createElement("span");s.className="pill kategori-renk";s.textContent=ad;s.style.background=kategoriRenk(ad);td.appendChild(s);tr.appendChild(td);return td;}
var bildirimZamanlayici=null;
function basari(m){var b=$("bildirim");b.textContent=m;b.classList.add("gorunur");clearTimeout(bildirimZamanlayici);bildirimZamanlayici=setTimeout(function(){b.classList.remove("gorunur");},2500);}
function sorgu(){
  var p=new URLSearchParams();
  if($("f-ay").value)p.set("ay",$("f-ay").value);
  if($("f-kategori").value.trim())p.set("kategori",$("f-kategori").value.trim());
  return p.toString();
}
async function listele(){
  try{
    var q=sorgu();
    $("csv").href="/export.csv"+(q?"?"+q:"");
    var v=await istek("/api/harcamalar"+(q?"?"+q:""));
    var gov=$("liste");gov.textContent="";
    if(!v.harcamalar.length){
      var t=document.createElement("tr");var d=hucre(t,"Kayıt yok.","bos");d.colSpan=5;gov.appendChild(t);
    }
    v.harcamalar.forEach(function(h){
      var tr=document.createElement("tr");
hucre(tr,h.tarih);kategoriHucre(tr,h.kategori);hucre(tr,h.aciklama||"");hucre(tr,h.tutar,"sayi tutar");
      var son=document.createElement("td");var b=document.createElement("button");
      b.type="button";b.className="sil";b.textContent="Sil";
      b.addEventListener("click",function(){sil(h.id);});
      son.appendChild(b);tr.appendChild(son);gov.appendChild(tr);
    });
    mesaj("");
  }catch(e){mesaj(e.message);}
rapor();
  ozet();
}
async function rapor(){
  var gov=$("rapor");gov.textContent="";
  var ay=$("f-ay").value;
  if(!ay){$("rapor-ozet").textContent="Rapor için yukarıdan bir ay seçin.";return;}
  try{
    var r=await istek("/api/rapor?ay="+encodeURIComponent(ay));
    $("rapor-ozet").textContent=r.ay+" genel toplam: "+r.genel_toplam;
    r.satirlar.forEach(function(s){
      var tr=document.createElement("tr");
var td=kategoriHucre(tr,s.kategori);var c=document.createElement("div");c.className="cubuk";var b=document.createElement("span");b.style.width=Math.min(100,Math.max(0,parseFloat(s.yuzde)||0))+"%";b.style.background=kategoriRenk(s.kategori);c.appendChild(b);td.appendChild(c);hucre(tr,s.tutar,"sayi tutar");hucre(tr,"%"+s.yuzde,"sayi");gov.appendChild(tr);
    });
  }catch(e){mesaj(e.message);}
}
async function ozet(){
  var ay=$("f-ay").value;
  if(!ay){var d=new Date();ay=d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0");}
  $("ozet-ay").textContent=ay;
  try{
    var r=await istek("/api/rapor?ay="+encodeURIComponent(ay));
    var h=await istek("/api/harcamalar?ay="+encodeURIComponent(ay));
    var en=null;
    r.satirlar.forEach(function(s){if(!en||s.tutar_kurus>en.tutar_kurus)en=s;});
    $("ozet-toplam").textContent=r.genel_toplam;
    $("ozet-adet").textContent=String(h.harcamalar.length);
    $("ozet-kategori").textContent=en?en.kategori:"—";
  }catch(e){mesaj(e.message);}
}
async function sil(id){
  if(!confirm("Bu harcama silinsin mi?"))return;
  try{await istek("/api/harcamalar/"+id,{method:"DELETE"});listele();}
  catch(e){mesaj(e.message);}
}
$("ekle-formu").addEventListener("submit",async function(o){
  o.preventDefault();
  var f=new FormData(o.target);var g={};
  f.forEach(function(d,k){if(String(d).trim()!=="")g[k]=String(d).trim();});
  try{
    await istek("/api/harcamalar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(g)});
o.target.reset();basari("Harcama eklendi.");listele();
  }catch(e){mesaj(e.message);}
});
$("filtrele").addEventListener("click",listele);
var temalar=["otomatik","açık","koyu"];
var tema=localStorage.getItem("tema")||"otomatik";
function temaUygula(){
  var k=document.documentElement;
  if(tema==="otomatik")k.removeAttribute("data-tema");else k.setAttribute("data-tema",tema);
  $("tema").textContent="Tema: "+tema;
}
$("tema").addEventListener("click",function(){
  tema=temalar[(temalar.indexOf(tema)+1)%temalar.length];
  localStorage.setItem("tema",tema);temaUygula();
});
temaUygula();
listele();
})();
</script>
</body>
</html>
"""


class IstekHatasi(Exception):
    """HTTP durum kodu ile birlikte gönderilecek istemci hatası."""

    def __init__(self, durum: int, mesaj: str) -> None:
        super().__init__(mesaj)
        self.durum = durum


@contextmanager
def _veritabani_ac(yol: str) -> Iterator[Veritabani]:
    veritabani = Veritabani(yol)
    try:
        yield veritabani
    finally:
        veritabani.kapat()


def _harcama_json(h: Harcama) -> Dict[str, Any]:
    return {
        "id": h.id,
        "tarih": h.tarih,
        "kategori": h.kategori,
        "tutar_kurus": h.tutar_kurus,
        "tutar": kurus_metni(h.tutar_kurus),
        "aciklama": h.aciklama,
    }


def _rapor_json(rapor: AylikRapor) -> Dict[str, Any]:
    return {
        "ay": rapor.ay,
        "genel_toplam_kurus": rapor.genel_toplam_kurus,
        "genel_toplam": kurus_metni(rapor.genel_toplam_kurus),
        "satirlar": [
            {
                "kategori": s.kategori,
                "tutar_kurus": s.tutar_kurus,
                "tutar": kurus_metni(s.tutar_kurus),
                "yuzde": str(s.yuzde),
            }
            for s in rapor.satirlar
        ],
    }


def _sorgu_tek(sorgu: Dict[str, List[str]], ad: str) -> Optional[str]:
    degerler = sorgu.get(ad)
    return degerler[0] if degerler else None


def _metin_alani(govde: Dict[str, Any], ad: str) -> Optional[str]:
    deger = govde.get(ad)
    if deger is None or isinstance(deger, str):
        return deger
    raise HarcamaHatasi(f"'{ad}' metin olmalı.")


def _tutar_alani(govde: Dict[str, Any]) -> str:
    deger = govde.get("tutar")
    if deger is None:
        raise HarcamaHatasi("'tutar' zorunlu. Örnek: \"150.50\".")
    # JSON sayıları float olarak gelir; kuruş hassasiyeti için metin ya da
    # tam sayı kabul edilir, ondalıklı JSON sayısı reddedilir.
    if isinstance(deger, bool) or not isinstance(deger, (str, int)):
        raise HarcamaHatasi("'tutar' metin (ör. \"150.50\") ya da tam sayı olmalı.")
    return str(deger)


class _Istekci(BaseHTTPRequestHandler):
    server_version = "HarcamaTakip/1.0"

    def do_GET(self) -> None:
        self._yonlendir("GET")

    def do_POST(self) -> None:
        self._yonlendir("POST")

    def do_DELETE(self) -> None:
        self._yonlendir("DELETE")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Testlerde ve kullanımda konsol gürültüsünü kapat.
        return

    # --- yönlendirme ---------------------------------------------------

    def _yonlendir(self, yontem: str) -> None:
        try:
            yol = urlsplit(self.path)
            sorgu = parse_qs(yol.query, keep_blank_values=True)
            self._islem(yontem, yol.path, sorgu)
        except HarcamaBulunamadi as hata:
            self._json(404, {"hata": str(hata)})
        except HarcamaHatasi as hata:
            self._json(400, {"hata": str(hata)})
        except IstekHatasi as hata:
            self._json(hata.durum, {"hata": str(hata)})
        except Exception:  # noqa: BLE001 - istemciye sabit bir hata dön
            traceback.print_exc()
            self._json(500, {"hata": "Beklenmeyen sunucu hatası."})

    def _islem(self, yontem: str, yol: str, sorgu: Dict[str, List[str]]) -> None:
        if yol == "/" and yontem == "GET":
            return self._sayfa()
        if yol == "/api/harcamalar":
            if yontem == "GET":
                return self._listele(sorgu)
            if yontem == "POST":
                return self._ekle()
        elif yol.startswith("/api/harcamalar/") and yontem == "DELETE":
            return self._sil(yol[len("/api/harcamalar/"):])
        elif yol == "/api/rapor" and yontem == "GET":
            return self._rapor(sorgu)
        elif yol == "/export.csv" and yontem == "GET":
            return self._csv(sorgu)
        raise IstekHatasi(404, "Bulunamadı.")

    # --- uç noktalar ---------------------------------------------------

    def _sayfa(self) -> None:
        self._yanit(200, "text/html; charset=utf-8", SAYFA_HTML.encode("utf-8"))

    def _listele(self, sorgu: Dict[str, List[str]]) -> None:
        ay = _sorgu_tek(sorgu, "ay")
        kategori = _sorgu_tek(sorgu, "kategori")
        with _veritabani_ac(self.server.db_yolu) as v:  # type: ignore[attr-defined]
            kayitlar = v.listele(ay, kategori)
        self._json(200, {"harcamalar": [_harcama_json(k) for k in kayitlar]})

    def _ekle(self) -> None:
        govde = self._govde_oku()
        tutar = _tutar_alani(govde)
        kategori = _metin_alani(govde, "kategori")
        tarih = _metin_alani(govde, "tarih")
        aciklama = _metin_alani(govde, "aciklama")
        with _veritabani_ac(self.server.db_yolu) as v:  # type: ignore[attr-defined]
            h = v.ekle(tutar, kategori or "", tarih, aciklama or "")
        self._json(201, _harcama_json(h))

    def _sil(self, id_metni: str) -> None:
        try:
            harcama_id = int(id_metni)
        except ValueError:
            raise IstekHatasi(400, "Geçersiz id: tam sayı olmalı.") from None
        with _veritabani_ac(self.server.db_yolu) as v:  # type: ignore[attr-defined]
            v.sil(harcama_id)
        self._json(200, {"silindi": harcama_id})

    def _rapor(self, sorgu: Dict[str, List[str]]) -> None:
        ay = _sorgu_tek(sorgu, "ay")
        if ay is None:
            raise IstekHatasi(400, "'ay' parametresi zorunlu (YYYY-AA).")
        with _veritabani_ac(self.server.db_yolu) as v:  # type: ignore[attr-defined]
            rapor = aylik_rapor(v, ay)
        self._json(200, _rapor_json(rapor))

    def _csv(self, sorgu: Dict[str, List[str]]) -> None:
        ay = _sorgu_tek(sorgu, "ay")
        kategori = _sorgu_tek(sorgu, "kategori")
        with _veritabani_ac(self.server.db_yolu) as v:  # type: ignore[attr-defined]
            kayitlar = v.listele(ay, kategori)
        akis = io.StringIO(newline="")
        csv_akisa_yaz(kayitlar, akis)
        self._yanit(
            200,
            "text/csv; charset=utf-8",
            akis.getvalue().encode("utf-8"),
            ek_basliklar=[("Content-Disposition", 'attachment; filename="harcamalar.csv"')],
        )

    # --- yardımcılar ---------------------------------------------------

    def _govde_oku(self) -> Dict[str, Any]:
        ham_uzunluk = self.headers.get("Content-Length") or "0"
        try:
            uzunluk = int(ham_uzunluk)
        except ValueError:
            raise IstekHatasi(400, "Geçersiz Content-Length.") from None
        if uzunluk <= 0:
            raise IstekHatasi(400, "İstek gövdesi boş olamaz (JSON bekleniyor).")
        if uzunluk > EN_BUYUK_GOVDE:
            raise IstekHatasi(413, "İstek gövdesi çok büyük.")
        ham = self.rfile.read(uzunluk)
        try:
            veri = json.loads(ham.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise IstekHatasi(400, "Gövde geçerli bir JSON değil.") from None
        if not isinstance(veri, dict):
            raise IstekHatasi(400, "Gövde bir JSON nesnesi olmalı.")
        return veri

    def _json(self, durum: int, veri: Any) -> None:
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self._yanit(durum, "application/json; charset=utf-8", govde)

    def _yanit(
        self,
        durum: int,
        icerik_tipi: str,
        govde: bytes,
        ek_basliklar: Sequence[Tuple[str, str]] = (),
    ) -> None:
        self.send_response(durum)
        self.send_header("Content-Type", icerik_tipi)
        self.send_header("Content-Length", str(len(govde)))
        for ad, deger in ek_basliklar:
            self.send_header(ad, deger)
        self.end_headers()
        self.wfile.write(govde)


class HarcamaSunucusu(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, adres: Tuple[str, int], db_yolu: str) -> None:
        super().__init__(adres, _Istekci)
        self.db_yolu = db_yolu


def sunucu_olustur(host: str, port: int, db_yolu: Optional[str]) -> HarcamaSunucusu:
    """Sunucuyu bağlar (dinlemeye başlamaz). ``port=0`` boş bir port seçtirir.

    Veritabanı şeması bu aşamada oluşturulur; çözümlenmiş DB yolu sunucuya verilir.
    """
    v = Veritabani(db_yolu)
    yol = v.yol
    v.kapat()
    return HarcamaSunucusu((host, port), yol)


def ana(argv: Optional[Sequence[str]] = None) -> int:
    ayristirici = argparse.ArgumentParser(
        prog="harcama-takip-web",
        description="Harcama Takip JSON API ve tarayıcı sunucusu.",
    )
    ayristirici.add_argument("--host", default=VARSAYILAN_HOST, help="Dinlenecek adres")
    ayristirici.add_argument("--port", type=int, default=VARSAYILAN_PORT, help="Port (varsayılan 8000)")
    ayristirici.add_argument(
        "--db",
        default=None,
        help="Veritabanı dosya yolu (varsayılan: HARCAMA_DB ortam değişkeni ya da harcamalar.db)",
    )
    args = ayristirici.parse_args(argv)
    try:
        sunucu = sunucu_olustur(args.host, args.port, args.db)
    except OSError as hata:
        print(f"Hata: sunucu başlatılamadı: {hata}", file=sys.stderr)
        return 1
    adres_host, adres_port = sunucu.server_address[:2]
    print(f"Harcama Takip sunucusu: http://{adres_host}:{adres_port} (veritabanı: {sunucu.db_yolu})")
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sunucu.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(ana())
