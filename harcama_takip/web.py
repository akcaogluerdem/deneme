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
:root{--bg:#f6f7f9;--kart:#fff;--yazi:#1c1e21;--soluk:#667085;--cizgi:#d9dde3;--vurgu:#2563eb;--tehlike:#c62828}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--kart:#1e2127;--yazi:#e8eaed;--soluk:#9aa3b2;--cizgi:#343a45;--vurgu:#6ea0ff;--tehlike:#ef6b6b}}
html[data-tema="koyu"]{--bg:#14161a;--kart:#1e2127;--yazi:#e8eaed;--soluk:#9aa3b2;--cizgi:#343a45;--vurgu:#6ea0ff;--tehlike:#ef6b6b}
html[data-tema="açık"]{--bg:#f6f7f9;--kart:#fff;--yazi:#1c1e21;--soluk:#667085;--cizgi:#d9dde3;--vurgu:#2563eb;--tehlike:#c62828}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--yazi)}
header,main{max-width:960px;margin:0 auto;padding:12px 16px}
header{display:flex;justify-content:space-between;align-items:center}
h1{font-size:1.4rem;margin:0}
section{background:var(--kart);border:1px solid var(--cizgi);border-radius:10px;padding:14px;margin-bottom:16px}
h2{font-size:1.1rem;margin:0 0 10px}
form,.filtre{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;align-items:end}
label{display:flex;flex-direction:column;font-size:.85rem;color:var(--soluk);gap:3px}
input,button{font:inherit;padding:8px;border-radius:6px;border:1px solid var(--cizgi);background:var(--bg);color:var(--yazi)}
button{background:var(--vurgu);color:#fff;border-color:var(--vurgu);cursor:pointer}
button.ikincil{background:transparent;color:var(--vurgu)}
button.sil{background:transparent;color:var(--tehlike);border-color:var(--tehlike);padding:4px 8px}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:6px;border-bottom:1px solid var(--cizgi);font-size:.92rem}
td.sayi,th.sayi{text-align:right}
.tablo{overflow-x:auto}
#mesaj{min-height:1.2em;color:var(--tehlike);margin:0 0 8px}
.bos{color:var(--soluk)}
a{color:var(--vurgu)}
@media (max-width:480px){header{flex-direction:column;align-items:flex-start;gap:6px}}
</style>
</head>
<body>
<header>
<h1>Harcama Takip</h1>
<button type="button" id="tema" class="ikincil">Tema: otomatik</button>
</header>
<main>
<p id="mesaj" role="alert"></p>
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
<section>
<h2>Harcamalar</h2>
<div class="filtre">
<label>Ay<input id="f-ay" type="month"></label>
<label>Kategori<input id="f-kategori" placeholder="tümü"></label>
<button type="button" id="filtrele">Filtrele</button>
<a id="csv" href="/export.csv" download="harcamalar.csv">CSV dışa aktar</a>
</div>
<div class="tablo">
<table>
<thead><tr><th>Tarih</th><th>Kategori</th><th>Açıklama</th><th class="sayi">Tutar</th><th></th></tr></thead>
<tbody id="liste"></tbody>
</table>
</div>
</section>
<section>
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
      hucre(tr,h.tarih);hucre(tr,h.kategori);hucre(tr,h.aciklama||"");hucre(tr,h.tutar,"sayi");
      var son=document.createElement("td");var b=document.createElement("button");
      b.type="button";b.className="sil";b.textContent="Sil";
      b.addEventListener("click",function(){sil(h.id);});
      son.appendChild(b);tr.appendChild(son);gov.appendChild(tr);
    });
    mesaj("");
  }catch(e){mesaj(e.message);}
  rapor();
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
      hucre(tr,s.kategori);hucre(tr,s.tutar,"sayi");hucre(tr,"%"+s.yuzde,"sayi");gov.appendChild(tr);
    });
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
    o.target.reset();listele();
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
