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


SAYFA_TASARIM = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Harcama Takip</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--zemin:#F4F5FA;--kart:#FFFFFF;--kenar:#E6E8F0;--ayrac:#EEF0F5;--metin:#111827;--metin-2:#4B5563;--girdi-zemin:#F8F9FC;--girdi-kenar:#DDE1EA;--bas:#111827;--bas-2:#1F2937;--bas-kenar:#374151;--bas-soluk:#C7CBD6;--birincil:#4338CA;--uzerine:#FFFFFF;--hata:#DC2626;--sil:#B91C1C;--basari:#16A34A;--zebra:#FAFBFD;--thead:#F8F9FC;--vurgu:#4338CA;--tehlike:#DC2626}
html[data-tema="koyu"]{--zemin:#0B1020;--kart:#141A2E;--kenar:#232B45;--ayrac:#1D2439;--metin:#F3F4F6;--metin-2:#A7AFC2;--girdi-zemin:#0F1528;--girdi-kenar:#2E3650;--birincil:#6366F1;--uzerine:#0B1020;--hata:#F87171;--sil:#F87171;--basari:#22C55E;--zebra:#171D33;--thead:#0F1528;--vurgu:#6366F1;--tehlike:#F87171}
@media (prefers-color-scheme: dark){html:not([data-tema="acik"]){--zemin:#0B1020;--kart:#141A2E;--kenar:#232B45;--ayrac:#1D2439;--metin:#F3F4F6;--metin-2:#A7AFC2;--girdi-zemin:#0F1528;--girdi-kenar:#2E3650;--birincil:#6366F1;--uzerine:#0B1020;--hata:#F87171;--sil:#F87171;--basari:#22C55E;--zebra:#171D33;--thead:#0F1528;--vurgu:#6366F1;--tehlike:#F87171}}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;font-family:"Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--zemin);color:var(--metin);font-variant-numeric:tabular-nums}
button,input,select,a{font:inherit}
button{cursor:pointer}
.gizli{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.bant{background:#111827;color:#fff;padding:18px 40px;display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
.marka{display:flex;align-items:center;gap:14px}
.logo{width:40px;height:40px;border-radius:12px;background:#4F46E5;display:grid;place-items:center;flex:none}
.marka h1{font-size:20px;font-weight:800;margin:0;line-height:1.2}
.marka p{margin:2px 0 0;font-size:13px;color:#C7CBD6}
.bant-sag{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ay-sec{display:flex;align-items:center;gap:8px;font-size:14px;color:#C7CBD6}
.girdi-bant{height:44px;border-radius:12px;border:1px solid #374151;background:#1F2937;color:#fff;padding:0 12px;color-scheme:dark}
.cerceve{height:44px;padding:0 16px;border:1px solid #374151;border-radius:12px;background:transparent;color:#fff;display:inline-flex;align-items:center;justify-content:center;gap:8px;font-weight:700;text-decoration:none}
.tema-dugme{width:44px;height:44px;border-radius:12px;border:1px solid #374151;background:transparent;color:#fff;display:grid;place-items:center;padding:0}
.icerik{max-width:1280px;margin:0 auto;padding:32px 40px;display:grid;gap:24px}
.ozet{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px}
.ozet-kart{background:var(--kart);border:1px solid var(--kenar);border-radius:18px;padding:22px;position:relative;color:var(--metin)}
.ozet-kart.dolu{background:#4338CA;border-color:#4338CA;color:#fff}
.ozet-kart .etiket{font-size:13px;font-weight:600;color:var(--metin-2)}
.ozet-kart.dolu .etiket,.ozet-kart.dolu .altyazi{color:#E0E7FF}
.tutar34{font-size:34px;font-weight:800;margin-top:6px;line-height:1.1}
.buyuk{font-size:26px;font-weight:800;margin-top:6px}
.altyazi{font-size:13px;color:var(--metin-2);margin-top:6px}
.ikon-kutu{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;margin-bottom:12px}
#ozet-kategori-pay{color:var(--birincil);font-weight:800;font-size:15px}
.satir{display:flex;flex-wrap:wrap;gap:24px}
.sol{flex:999 1 560px;min-width:0}
.sag{flex:1 1 360px;display:grid;gap:24px;align-content:start;min-width:0}
.kart{background:var(--kart);border:1px solid var(--kenar);border-radius:18px;padding:22px;color:var(--metin)}
.baslik{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.baslik h2{font-size:18px;font-weight:800;margin:0;display:flex;gap:8px;align-items:center}
.rozet{background:#EEF0FF;color:#3730A3;border-radius:999px;padding:2px 10px;font-size:13px;font-weight:700}
.soluk{color:var(--metin-2)}
.girdi,#kategori-sec{height:44px;border:1px solid var(--girdi-kenar);background:var(--girdi-zemin);color:var(--metin);border-radius:12px;padding:0 12px;width:100%}
.kat-sec{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--metin-2);font-weight:600}
.kat-sec select{width:auto;min-width:180px}
.tablo-kap{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{background:var(--thead);font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--metin-2);text-align:left;padding:10px 12px}
td{padding:12px;border-top:1px solid var(--ayrac);font-size:14px;vertical-align:middle}
tbody tr:nth-child(even){background:var(--zebra)}
th.sayi,td.sayi{text-align:right}
td.tutar{font-weight:700;text-align:right;white-space:nowrap}
tfoot td{font-weight:800;border-top:1px solid var(--kenar)}
.pill{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}
td.bos{color:var(--metin-2);text-align:center}
.islem{width:56px}
.sil{width:44px;height:44px;border:1px solid #FBD5D5;background:#fff;color:#B91C1C;border-radius:12px;display:grid;place-items:center;padding:0}
.sil:hover{background:#FEF2F2}
.bos-kutu{border:1px dashed var(--kenar);border-radius:14px;padding:32px;text-align:center;color:var(--metin-2);margin-top:12px}
.bos-kutu strong{display:block;color:var(--metin);font-size:16px;margin-bottom:4px}
#mesaj{display:none;background:#FEF2F2;border:1px solid #FECACA;color:#991B1B;border-radius:12px;padding:12px 14px;font-size:14px;margin:0}
#mesaj.acik{display:block}
.girdi[aria-invalid="true"],.tutar-girdi[aria-invalid="true"]{border:2px solid var(--hata)}
.yigin{display:flex;gap:2px;height:14px;border-radius:999px;overflow:hidden;margin-bottom:16px;background:var(--ayrac)}
.cubuk{display:block;height:100%;min-width:0}
.dag-satir{display:grid;grid-template-columns:14px 1fr auto auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid var(--ayrac);font-size:14px}
.kare{width:14px;height:14px;border-radius:4px}
.dag-satir .tutar{font-weight:700}
.genel{display:flex;justify-content:space-between;align-items:center;margin-top:14px;font-size:20px;font-weight:800}
.form{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form .tam{grid-column:1/-1}
.lbl{display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:600;color:var(--metin-2)}
.tutar-kutu{position:relative}
.tutar-kutu>span{position:absolute;left:16px;top:50%;transform:translateY(-50%);font-size:28px;font-weight:800;color:var(--metin-2);pointer-events:none}
.tutar-girdi{height:72px;width:100%;border:1px solid var(--girdi-kenar);background:var(--girdi-zemin);color:var(--metin);border-radius:14px;padding:0 16px 0 44px;font-size:48px;font-weight:800}
.hizli{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.chip{min-height:44px;padding:0 14px;border-radius:999px;border:0;font-weight:700}
.birincil,.birincil-m{height:52px;border:0;border-radius:14px;background:var(--birincil);color:var(--uzerine);font-weight:800;width:100%}
.kapat-mobil{display:none}
.dagilim-kart .genel span:last-child{color:var(--metin)}
#bildirim{position:fixed;right:24px;bottom:24px;background:#111827;color:#fff;border-radius:14px;padding:14px 18px;display:none;gap:12px;align-items:center;box-shadow:0 10px 30px rgba(0,0,0,.25);z-index:30}
#bildirim.acik{display:flex}
#bildirim strong{display:block;font-size:15px}
#bildirim small{color:#C7CBD6;font-size:13px}
dialog{border:0;border-radius:18px;padding:24px;background:var(--kart);color:var(--metin);max-width:420px;width:calc(100% - 32px)}
dialog::backdrop{background:rgba(17,24,39,.5)}
dialog h3{margin:0 0 8px;font-size:18px;font-weight:800}
.dlg-btn{display:flex;gap:10px;justify-content:flex-end;margin:20px 0 0}
.dlg-btn button{height:44px;padding:0 18px;border-radius:12px;font-weight:700;border:1px solid var(--kenar);background:transparent;color:var(--metin)}
.dlg-btn .tehlike{background:var(--sil);border-color:var(--sil);color:#fff}
.mobil-only,.mobil-tarih{display:none}
.segment,.alt-cubuk{display:none}
.mini{margin:12px 0 6px;height:8px}
@media (max-width:640px){
.bant{padding:18px 20px 72px}
.bant .cerceve{display:none}
.icerik{padding:0 16px 140px;gap:16px}
.ozet-kart:first-child{margin-top:-56px}
.mobil-only{display:block}
.mobil-tarih{display:block;color:var(--metin-2);font-size:12px}
.segment{display:flex;background:var(--kart);border:1px solid var(--kenar);border-radius:12px;padding:4px;gap:4px}
.segment button{flex:1;height:44px;border:0;border-radius:9px;background:transparent;color:var(--metin-2);font-weight:700}
.segment button[aria-pressed="true"]{background:var(--birincil);color:var(--uzerine)}
.tarih-s{display:none}
thead{display:none}
#liste tr{display:grid;grid-template-columns:auto 1fr auto auto;gap:8px;align-items:center;padding:8px 0;border-bottom:1px solid var(--ayrac)}
#liste td{border:0;padding:4px}
#liste td.tutar{text-align:right}
#liste td.islem{width:44px}
tfoot{display:none}
[data-gorunum="rapor"] .sol{display:none}
[data-gorunum="liste"] .dagilim-kart{display:none}
.sag{display:flex;flex-direction:column;gap:16px}
.form-kart{position:fixed;left:0;right:0;bottom:0;max-height:80vh;overflow:auto;border-radius:18px 18px 0 0;transform:translateY(105%);transition:transform .2s;z-index:20;margin:0}
.ekle-acik .form-kart{transform:none}
.kapat-mobil{display:block;height:44px;padding:0 14px;border-radius:12px;border:1px solid var(--kenar);background:transparent;color:var(--metin)}
.alt-cubuk{position:fixed;left:0;right:0;bottom:0;display:flex;gap:10px;padding:12px 16px;background:var(--kart);border-top:1px solid var(--kenar);z-index:10}
.alt-cubuk>*{height:54px;flex:1;border-radius:14px;display:flex;align-items:center;justify-content:center;font-weight:800;text-decoration:none}
.birincil-m{background:var(--birincil);color:var(--uzerine)}
.cerceve-m{border:1px solid var(--birincil);color:var(--birincil);background:transparent}
body.ekle-acik .alt-cubuk{display:none}
}
</style>
</head>
<body>
<header class="bant">
<div class="marka">
<div class="logo"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h13v4"/><rect x="3" y="7" width="18" height="13" rx="2"/><circle cx="16.5" cy="13.5" r="1.2"/></svg></div>
<div><h1>Harcama Takip</h1><p>Kişisel harcama defterin</p></div>
</div>
<div class="bant-sag">
<label class="ay-sec">Ay <input id="ay" type="month" class="girdi-bant"></label>
<a id="csv" class="cerceve" href="/export.csv">CSV indir</a>
<button type="button" id="tema" class="tema-dugme" aria-label="Temayı değiştir"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg><span id="tema-etiket" class="gizli"></span></button>
</div>
</header>
<main class="icerik" id="ana" data-gorunum="liste">
<div class="segment" role="group" aria-label="Görünüm">
<button type="button" data-g="liste" aria-pressed="true">Liste</button>
<button type="button" data-g="rapor" aria-pressed="false">Rapor</button>
</div>
<div class="ozet">
<div class="ozet-kart dolu">
<div class="etiket">Aylık toplam · <span id="ozet-ay">—</span></div>
<div class="tutar34" id="ozet-toplam">—</div>
<div class="altyazi" id="ozet-kat-ozet"></div>
<div class="mobil-only"><div class="yigin mini" id="ozet-mini"></div><span class="rozet" id="ozet-mobil-rozet"></span> <span class="altyazi" id="ozet-mobil-en"></span></div>
</div>
<div class="ozet-kart">
<div class="ikon-kutu" style="background:#CCFBF1;color:#0D9488"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10"/></svg></div>
<div class="etiket">Kayıt sayısı</div>
<div class="buyuk" id="ozet-adet">—</div>
<div class="altyazi" id="ozet-son"></div>
</div>
<div class="ozet-kart">
<div class="ikon-kutu" style="background:#FFEDD5;color:#EA580C"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.2"/></svg></div>
<div class="etiket">En çok harcanan</div>
<div class="buyuk" id="ozet-kategori">—</div>
<div id="ozet-kategori-pay"></div>
<div class="altyazi" id="ozet-kategori-tutar"></div>
</div>
</div>
<p id="mesaj" role="alert"></p>
<div class="satir">
<section class="kart sol" aria-labelledby="liste-baslik">
<div class="baslik">
<h2 id="liste-baslik">Harcamalar <span class="rozet" id="adet-rozet">0</span></h2>
<label class="kat-sec">Kategori <select id="kategori-sec"><option value="">Tüm kategoriler</option></select></label>
</div>
<div class="tablo-kap">
<table id="harcama-tablo">
<thead><tr><th class="tarih-s">Tarih</th><th>Kategori</th><th>Açıklama</th><th class="sayi">Tutar</th><th><span class="gizli">İşlem</span></th></tr></thead>
<tbody id="liste"></tbody>
<tfoot><tr><td class="tarih-s"></td><td>Toplam</td><td></td><td class="sayi tutar" id="liste-toplam">—</td><td></td></tr></tfoot>
</table>
</div>
<div class="bos-kutu" id="bos-ay" hidden><strong>Bu ayda kayıt yok</strong>İlk harcamanı ekleyerek başla.</div>
</section>
<div class="sag">
<section class="kart form-kart" id="ekle-kart" aria-labelledby="ekle-baslik">
<div class="baslik"><h2 id="ekle-baslik">Yeni harcama</h2><button type="button" class="kapat-mobil" id="ekle-kapat">Kapat</button></div>
<form id="ekle-formu" class="form" novalidate>
<div class="tam"><label class="lbl">Tutar<div class="tutar-kutu"><span aria-hidden="true">₺</span><input name="tutar" class="tutar-girdi" inputmode="decimal" placeholder="150.50" required></div></label></div>
<div class="tam"><label class="lbl">Kategori<input name="kategori" class="girdi" placeholder="market" autocomplete="off" required></label>
<div class="hizli" id="hizli" aria-label="Hızlı kategori seçimi"></div></div>
<label class="lbl">Tarih<input name="tarih" type="date" class="girdi"></label>
<label class="lbl">Açıklama<input name="aciklama" class="girdi" placeholder="isteğe bağlı"></label>
<div class="tam"><button type="submit" class="birincil">+ Harcama ekle</button></div>
</form>
</section>
<section class="kart dagilim-kart" aria-labelledby="dag-baslik">
<h2 id="dag-baslik" class="baslik" style="margin-bottom:12px">Kategori dağılımı</h2>
<div class="yigin" id="dagilim-yigin" role="img" aria-label="Kategori dağılımı"></div>
<div id="dagilim-satirlar"></div>
<p class="soluk" id="dagilim-bos" hidden>Bu ayda dağılım yok.</p>
<div class="genel"><span>Genel toplam</span><span id="genel-toplam">—</span></div>
</section>
</div>
</div>
</main>
<div class="alt-cubuk">
<button type="button" class="birincil-m" id="ekle-ac">+ Harcama ekle</button>
<a id="csv-alt" class="cerceve-m" href="/export.csv">CSV</a>
</div>
<dialog id="sil-diyalog" aria-labelledby="sil-baslik">
<h3 id="sil-baslik">Harcama silinsin mi?</h3>
<p id="sil-ozet" class="soluk"></p>
<form method="dialog" class="dlg-btn">
<button type="submit" value="vazgec" id="sil-vazgec">Vazgeç</button>
<button type="submit" value="sil" id="sil-onay" class="tehlike">Sil</button>
</form>
</dialog>
<div id="bildirim" role="status"></div>
<script>
(function(){
"use strict";
var $=function(id){return document.getElementById(id);};
var AYLAR=["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];
var AYLAR_UZUN=["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
var SABIT={"market":0,"faturalar":1,"ulaşım":2,"yemek":3};
var PALET=["#4F46E5","#DB2777","#0D9488","#EA580C","#CA8A04","#16A34A","#9333EA","#475569"];
var PALET_ZEMIN=["#EEF0FF","#FCE7F3","#CCFBF1","#FFEDD5","#FEF9C3","#DCFCE7","#F3E8FF","#F1F5F9"];
var PALET_METIN=["#3730A3","#9D174D","#115E59","#9A3412","#854D0E","#166534","#6B21A8","#334155"];
var HIZLI=["market","faturalar","ulaşım","yemek"];
var ONAY_SVG='<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>';
var COP_SVG='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>';
var ETIKET={"otomatik":"otomatik","acik":"açık","koyu":"koyu"};
var TEMALAR=["otomatik","acik","koyu"];
var silHedef=null;
var zamanlayici=null;

function indeks(ad){
  if(Object.prototype.hasOwnProperty.call(SABIT,ad))return SABIT[ad];
  var h=0;for(var i=0;i<ad.length;i++){h=(h*31+ad.charCodeAt(i))>>>0;}
  return h%PALET.length;
}
function kategoriRenk(ad){return PALET[indeks(ad)];}
function hap(ad){var i=indeks(ad);var s=document.createElement("span");s.className="pill kategori-renk";s.textContent=ad;s.style.background=PALET_ZEMIN[i];s.style.color=PALET_METIN[i];return s;}
function hucre(tr,metin,sinif){var td=document.createElement("td");td.textContent=metin;if(sinif)td.className=sinif;tr.appendChild(td);return td;}
function tarihKisa(t){var p=t.split("-");return p[2]+" "+AYLAR[parseInt(p[1],10)-1];}
function tarihSirala(a,b){if(a.tarih!==b.tarih)return a.tarih<b.tarih?1:-1;return b.id-a.id;}
function kurusMetin(k){return (k/100).toFixed(2).replace(".",",");}
function mesaj(m){var k=$("mesaj");k.textContent=m||"";k.classList.toggle("acik",!!m);}
function bildir(baslik,alt){
  var k=$("bildirim");k.textContent="";
  var s=document.createElement("span");s.innerHTML=ONAY_SVG;k.appendChild(s);
  var d=document.createElement("div");var st=document.createElement("strong");st.textContent=baslik;
  var sm=document.createElement("small");sm.textContent=alt;d.appendChild(st);d.appendChild(sm);k.appendChild(d);
  k.classList.add("acik");clearTimeout(zamanlayici);
  zamanlayici=setTimeout(function(){k.classList.remove("acik");},3000);
}
async function istek(url,secenek){
  var y=await fetch(url,secenek);var v=await y.json();
  if(!y.ok)throw new Error(v.hata||"İstek başarısız.");
  return v;
}
function aySec(){
  var a=$("ay").value;
  if(!a){var d=new Date();a=d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0");$("ay").value=a;}
  return a;
}
function alanHata(ad,hata){var e=$("ekle-formu").elements[ad];if(e)e.setAttribute("aria-invalid",hata?"true":"false");}

function kategoriSecenekleri(liste){
  var sel=$("kategori-sec");var onceki=sel.value;
  var adlar=[];liste.forEach(function(h){if(adlar.indexOf(h.kategori)<0)adlar.push(h.kategori);});
  adlar.sort();
  sel.textContent="";
  var t=document.createElement("option");t.value="";t.textContent="Tüm kategoriler";sel.appendChild(t);
  adlar.forEach(function(a){var o=document.createElement("option");o.value=a;o.textContent=a;sel.appendChild(o);});
  sel.value=adlar.indexOf(onceki)>=0?onceki:"";
}
function yigin(el,rap){
  el.textContent="";var etiketler=[];
  rap.satirlar.forEach(function(s){
    var c=document.createElement("span");c.className="cubuk";
    var pct=Math.max(0,parseFloat(s.yuzde)||0);
    c.style.flex="0 0 "+pct+"%";c.style.background=kategoriRenk(s.kategori);
    el.appendChild(c);etiketler.push(s.kategori+" %"+s.yuzde);
  });
  el.setAttribute("aria-label","Kategori dağılımı: "+(etiketler.join(", ")||"kayıt yok"));
}
function tabloCiz(liste,toplam){
  var gov=$("liste");gov.textContent="";
  var sirali=liste.slice().sort(tarihSirala);
  if(!sirali.length){
    var t0=document.createElement("tr");var d0=document.createElement("td");
    d0.colSpan=5;d0.className="bos";d0.textContent="Kayıt yok.";t0.appendChild(d0);gov.appendChild(t0);
  }
  sirali.forEach(function(h){
    var tr=document.createElement("tr");
    hucre(tr,tarihKisa(h.tarih),"tarih-s");
    var kt=document.createElement("td");kt.appendChild(hap(h.kategori));tr.appendChild(kt);
    var ac=document.createElement("td");ac.textContent=h.aciklama||"";
    var mt=document.createElement("small");mt.className="mobil-tarih";mt.textContent=tarihKisa(h.tarih);
    ac.appendChild(mt);tr.appendChild(ac);
    hucre(tr,"₺"+h.tutar,"tutar");
    var son=document.createElement("td");son.className="islem";
    var b=document.createElement("button");b.type="button";b.className="sil";
    b.setAttribute("aria-label",h.id+" numaralı harcamayı sil");b.innerHTML=COP_SVG;
    b.addEventListener("click",function(){sil(h);});
    son.appendChild(b);tr.appendChild(son);gov.appendChild(tr);
  });
  $("adet-rozet").textContent=String(sirali.length);
  $("liste-toplam").textContent=toplam;
}
function ozetCiz(ay,liste,rap){
  var p=ay.split("-");
  $("ozet-ay").textContent=AYLAR_UZUN[parseInt(p[1],10)-1]+" "+p[0];
  $("ozet-toplam").textContent="₺"+rap.genel_toplam;
  $("ozet-kat-ozet").textContent=rap.satirlar.length+" kategoride "+liste.length+" harcama";
  $("ozet-adet").textContent=String(liste.length);
  var sirali=liste.slice().sort(tarihSirala);
  $("ozet-son").textContent=sirali.length?"Son kayıt: "+tarihKisa(sirali[0].tarih):"";
  var en=null;rap.satirlar.forEach(function(s){if(!en||s.tutar_kurus>en.tutar_kurus)en=s;});
  $("ozet-kategori").textContent=en?en.kategori:"—";
  $("ozet-kategori-pay").textContent=en?"%"+en.yuzde:"";
  $("ozet-kategori-tutar").textContent=en?"₺"+en.tutar+" · "+liste.filter(function(h){return h.kategori===en.kategori;}).length+" harcama":"";
  $("ozet-mobil-rozet").textContent=liste.length+" kayıt";
  $("ozet-mobil-en").textContent=en?"En çok: "+en.kategori+" · %"+en.yuzde:"";
  yigin($("ozet-mini"),rap);
}
function dagilimCiz(rap){
  yigin($("dagilim-yigin"),rap);
  var gov=$("dagilim-satirlar");gov.textContent="";
  rap.satirlar.forEach(function(s){
    var r=document.createElement("div");r.className="dag-satir";
    var k=document.createElement("span");k.className="kare";k.style.background=kategoriRenk(s.kategori);r.appendChild(k);
    var ad=document.createElement("span");ad.textContent=s.kategori;r.appendChild(ad);
    var t=document.createElement("span");t.className="tutar";t.textContent="₺"+s.tutar;r.appendChild(t);
    var y=document.createElement("span");y.className="sayi soluk";y.textContent="%"+s.yuzde;r.appendChild(y);
    gov.appendChild(r);
  });
  $("genel-toplam").textContent="₺"+rap.genel_toplam;
  $("dagilim-bos").hidden=rap.satirlar.length>0;
}
async function yukle(){
  try{
    var ay=aySec();
    var tum=await istek("/api/harcamalar?ay="+encodeURIComponent(ay));
    var rap=await istek("/api/rapor?ay="+encodeURIComponent(ay));
    kategoriSecenekleri(tum.harcamalar);
    var kat=$("kategori-sec").value;
    var liste=kat?tum.harcamalar.filter(function(h){return h.kategori===kat;}):tum.harcamalar;
    var toplam=kat?"₺"+kurusMetin(liste.reduce(function(a,h){return a+h.tutar_kurus;},0)):"₺"+rap.genel_toplam;
    tabloCiz(liste,toplam);
    $("bos-ay").hidden=tum.harcamalar.length>0;
    var q="/export.csv?ay="+encodeURIComponent(ay)+(kat?"&kategori="+encodeURIComponent(kat):"");
    $("csv").href=q;$("csv-alt").href=q;
    ozetCiz(ay,tum.harcamalar,rap);
    dagilimCiz(rap);
    mesaj("");
  }catch(e){mesaj(e.message);}
}
function sil(h){
  silHedef=h;
  $("sil-ozet").textContent="#"+h.id+" · "+h.kategori+" · ₺"+h.tutar;
  $("sil-diyalog").showModal();
}
$("sil-diyalog").addEventListener("close",async function(){
  if($("sil-diyalog").returnValue!=="sil"||!silHedef)return;
  var id=silHedef.id;silHedef=null;
  try{
    await istek("/api/harcamalar/"+id,{method:"DELETE"});
    bildir("Harcama silindi","#"+id);
    await yukle();
  }catch(e){mesaj(e.message);}
});
$("ekle-formu").addEventListener("submit",async function(o){
  o.preventDefault();
  var f=o.target;var g={};
  ["tutar","kategori","tarih","aciklama"].forEach(function(ad){var v=f.elements[ad].value.trim();if(v!=="")g[ad]=v;});
  alanHata("tutar",false);alanHata("kategori",false);
  try{
    var h=await istek("/api/harcamalar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(g)});
    f.reset();
    document.body.classList.remove("ekle-acik");
    bildir("Harcama eklendi","#"+h.id+" · "+h.kategori+" · ₺"+h.tutar);
    await yukle();
  }catch(e){
    mesaj(e.message);
    alanHata("tutar",/tutar/i.test(e.message));
    alanHata("kategori",/kategori/i.test(e.message));
  }
});
var hizliGov=$("hizli");
HIZLI.forEach(function(ad){
  var b=document.createElement("button");b.type="button";b.className="chip";b.textContent=ad;
  var i=indeks(ad);b.style.background=PALET_ZEMIN[i];b.style.color=PALET_METIN[i];
  b.addEventListener("click",function(){$("ekle-formu").elements.kategori.value=ad;alanHata("kategori",false);});
  hizliGov.appendChild(b);
});
document.querySelectorAll(".segment button").forEach(function(b){
  b.addEventListener("click",function(){
    $("ana").setAttribute("data-gorunum",b.getAttribute("data-g"));
    document.querySelectorAll(".segment button").forEach(function(x){x.setAttribute("aria-pressed",x===b?"true":"false");});
  });
});
$("ekle-ac").addEventListener("click",function(){document.body.classList.add("ekle-acik");$("ekle-formu").elements.tutar.focus();});
$("ekle-kapat").addEventListener("click",function(){document.body.classList.remove("ekle-acik");});
$("ay").addEventListener("change",yukle);
$("kategori-sec").addEventListener("change",yukle);
var tema=localStorage.getItem("tema")||"otomatik";
if(TEMALAR.indexOf(tema)<0)tema="otomatik";
function temaUygula(){
  var k=document.documentElement;
  if(tema==="otomatik")k.removeAttribute("data-tema");else k.setAttribute("data-tema",tema);
  $("tema").title="Tema: "+ETIKET[tema];
  $("tema-etiket").textContent="Tema: "+ETIKET[tema];
}
$("tema").addEventListener("click",function(){
  tema=TEMALAR[(TEMALAR.indexOf(tema)+1)%TEMALAR.length];
  localStorage.setItem("tema",tema);temaUygula();
});
temaUygula();
aySec();
yukle();
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
        self._yanit(200, "text/html; charset=utf-8", SAYFA_TASARIM.encode("utf-8"))

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
