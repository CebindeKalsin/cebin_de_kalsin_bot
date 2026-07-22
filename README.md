# Cebin de Kalsın — Telegram Otomatik Paylaşım Botu

Bot'a özel mesaj (DM) olarak gönderdiğin her şeyi (link, fotoğraf+açıklama, video vb.)
otomatik olarak `t.me/Cebin_de_Kalsin` kanalına aynen kopyalar. Sadece senin
Telegram hesabından (OWNER_ID) gelen mesajlara tepki verir, başkası bot'a yazsa da
hiçbir şey olmaz.

## 1) Bot oluştur

1. Telegram'da **@BotFather**'a git, `/newbot` yaz, adını ve kullanıcı adını belirle.
2. Sana verdiği **token**'ı not al (örn. `123456789:AA...`).

## 2) Botu kanala admin yap

1. `t.me/Cebin_de_Kalsin` kanalına git → **Kanal Yönetimi → Yöneticiler → Yönetici Ekle**.
2. Az önce oluşturduğun botu ara ve ekle, **"Mesaj Gönder"** yetkisinin açık olduğundan emin ol.

## 3) Kendi Telegram User ID'ni öğren

1. Telegram'da **@userinfobot**'a `/start` yaz.
2. Sana verdiği **Id** değerini not al — bu senin `OWNER_ID`'n.

## 4a) Önce kendi bilgisayarında dene (opsiyonel ama önerilir)

```powershell
cd cebin_de_kalsin_bot
pip install -r requirements.txt
$env:BOT_TOKEN="botfather-token"
$env:CHANNEL_ID="@Cebin_de_Kalsin"
$env:OWNER_ID="123456789"
python bot.py
```

`WEBHOOK_URL` tanımlanmadığı için bot otomatik olarak **yerel (polling) modda**
başlar — internete açık bir adrese ihtiyaç duymaz. Terminal açık kaldığı sürece
çalışır; bot'una DM attığında kanala paylaşım yapar. Terminali kapatınca durur.

Buluta geçerken bu adımda **hiçbir kod değişikliği gerekmiyor** — sadece 5. adımda
`WEBHOOK_URL` ortam değişkenini eklemen yeterli, bot kendisi webhook moduna geçiyor.

## 4b) Kodu GitHub'a yükle

Yerelde test ettikten sonra, 7/24 çalışması için bu klasörü (`cebin_de_kalsin_bot`)
kendi GitHub hesabında bir repo'ya push et (Render, GitHub reposuna bağlanarak
deploy yapıyor).

## 5) Render.com'da deploy et

1. [render.com](https://render.com) üzerinde ücretsiz hesap aç, GitHub'ı bağla.
2. **New → Web Service** seç, yukarıdaki repo'yu seç.
3. Ayarlar:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** Free
4. Servisi oluşturduktan sonra Render sana bir URL verir
   (örn. `https://cebin-de-kalsin-bot.onrender.com`) — bunu not al.
5. **Environment** sekmesinden şu değişkenleri ekle:
   - `BOT_TOKEN` → BotFather'dan aldığın token
   - `CHANNEL_ID` → `@Cebin_de_Kalsin`
   - `OWNER_ID` → 3. adımda aldığın sayısal ID
   - `WEBHOOK_URL` → Render'ın sana verdiği URL (sonunda `/` olmadan)
6. Değişkenleri kaydet, servisi yeniden deploy et (Manual Deploy → Deploy latest commit).

## 6) Test et

Bot'una Telegram'dan DM olarak bir link, fotoğraf veya video+açıklama gönder.
Birkaç saniye içinde aynı içerik `Cebin_de_Kalsin` kanalında otomatik olarak
paylaşılmış olmalı ve bot sana "Kanala paylaşıldı." diye cevap verecek.

> Not: Render'ın ücretsiz planı 15 dakika hareketsiz kalınca servisi uyutur.
> Uzun süre sonra ilk mesajında paylaşım birkaç saniye gecikebilir, bu normaldir.

## Notlar / Sınırlar

- Bu bot yalnızca **Telegram kanalına** otomatik paylaşım yapar.
- WhatsApp Kanalı ve Instagram Kanalı (Broadcast Channel) için Meta'nın resmi bir
  otomatik paylaşım API'si yok; bu ikisi için ya elle paylaşım, ya da hesap
  kısıtlanma riski taşıyan ücretli üçüncü parti servisler (Wassenger, Whapi.Cloud vb.)
  gerekiyor. İstersen bu bot'u ileride bu servislerle genişletebiliriz.
