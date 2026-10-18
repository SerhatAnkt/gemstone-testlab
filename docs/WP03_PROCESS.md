# WP-03 — ortak süreç yönetimi ve temizlik

Kabul ölçütü: normal kapanan, hata veren ve takılan yardımcı süreçler yönetilir;
testin sahip olduğu süreç grubu ve dosya tanımlayıcıları temizlenir. Yerel Linux
ortamında 17 süreç kontrolü ve önceki 5 derleme kontrolünün tamamı geçti.

## API

```python
from pathlib import Path
import sys
import uuid
from tests.testlab.process import ManagedProcess

logs = Path("artifacts/demo") / uuid.uuid4().hex
with ManagedProcess([sys.executable, "-u", "-c", "print('READY', flush=True)"],
                    log_dir=logs) as process:
    process.expect(b"READY\n", timeout=5)
    process.wait(timeout=10)
print(process.record["status"])
```

| İşlem | Davranış |
| --- | --- |
| `ManagedProcess(argv, log_dir=...)` | argv listesini alır; shell açmaz; yeni günlük dizini ister |
| `with process:` | Ayrı oturum/grup içinde başlatır; çıkışta temizler |
| `expect(bytes, channel=..., timeout=...)` | Parçalı okumalar boyunca bayt işareti bekler; okuma imlecini ilerletir |
| `read_exact(n, channel=...)` | Son imleçten itibaren tam n bayt döndürür |
| `send(bytes)` | Stdin pipe'ına yazar; yazarken çıktı kanallarını da boşaltır |
| `send(bytes, fd=peer)` | Fixture'ın kaydettirdiği PTY master ucuna yazar |
| `close_input()` | Yöneticiye ait stdin pipe'ını kapatır |
| `wait(timeout=...)` | Gerçek dönüş kodunu döndürür; zaman aşımı hata olarak kalır |
| `signal(signum)` | Yalnızca sahip olunan gruba sinyal gönderir |
| `shutdown(signum=None, timeout=3)` | Varsayılan SIGTERM ile normal kapanışı dener |
| `close()` | Gerekirse grubu sonlandırır, toplar ve kayıtları tamamlar; tekrar çağrı güvenlidir |
| `run_process(...)` | Etkileşimsiz tek komut için aynı modülün kısa sarmalayıcısı |

Her nesnenin I/O çağrıları tek bir kontrol akışından yapılır. Aynı senaryoda birden
fazla yönetilen süreç bulunabilir; grupları ve günlükleri birbirinden ayrıdır.

## Süreler ve çıktı

| Bütçe | Varsayılan |
| --- | --- |
| Hazırlık işareti | 5 saniye |
| Bayt okuma/yazma | 5 saniye |
| Çalışmayı bekleme | 10 saniye |
| İstenen normal kapanış | 3 saniye |
| Temizlikte SIGTERM bekleme | 1 saniye |
| SIGKILL sonrası toplama | 2 saniye |

Bunlar ayrı aşama sınırlarıdır; gerçek zamanlı performans garantisi değildir.
Süreler monotonik saatle ölçülür; rapor zamanları UTC'dir. Süre değerleri sonlu
ve pozitif olmalıdır. Testler kısa bütçelerle kontrollü takılmaları sınar.

`selectors` ile stdout ve stderr birlikte okunur. Veri ham bayt olarak tutulur;
NUL baytı ve UTF-8 dışı veri metin dönüştürmesine uğramaz. Varsayılan çıktı sınırı
**kanal başına 1 MiB**; derleme sarmalayıcısında birleşik kanal için 8 MiB'dır.
Sınırı aşan çıktı başarısızlıktır; kesilme ve görülen/saklanan bayt sayıları kaydedilir.

## Temizlik ve sahiplik

1. Normal kapanış senaryosu uygulamadan beklenen dönüş kodunu doğrular.
2. Süreç hâlâ yaşıyorsa veya aynı grupta çocuk kaldıysa SIGTERM gönderilir.
3. Süre dolarsa SIGKILL gönderilir; zorla öldürme normal başarıya çevrilmez.
4. Doğrudan çocuk yalnızca kendi `Popen` nesnesiyle toplanır.
5. Yetim kalan aynı grup çocukları Linux child-subreaper mekanizmasıyla alınır
   ve yalnızca bu çocukların PID'lerine `waitpid` çağrılır. Genel `waitpid(-1)` yoktur.
6. Zombie dahil kalan grup üyeleri procfs üzerinden kontrol edilir.
7. Selector, yöneticiye ait pipe'lar ve günlükler kapatılır. Fixture'ın verdiği
   PTY descriptor'ları açık bırakılır ve değiştirilmiş nonblocking bayrakları geri alınır.

Subreaper durumu ilk aktif süreçte açılır; son yönetilen süreç kapandığında önceki
değere döner. İç içe süreçlerin ortak kullanımı referans sayısıyla izlenir.
Bu Linux API'si bu ortamda ayrıcalıksız olarak doğrulandı.

Procfs farklı bir PID ad alanından bağlanmış olabilir. Modül sinyal/wait için
çağıranın PID'sini, procfs taraması için önbelleğe alınmış procfs grup kimliğini
kullanır. `NSpid` ile çeviri yapar. Bu teslimin gerçek ortamında iki kimlik
farklıydı; kontroller bu durumda da geçti.

Sözleşme aynı süreç grubunda kalan hedefler içindir. Kendi `setsid`/grup değişimiyle
ayrılan daemon'lar izlenmez. Yönetici Linux procfs, `NSpid` ve child-subreaper
desteği ister; bir container içinde UID=0 olmayı önkoşul kabul etmez.

## Sonuçların anlamı

| Sonuç | Anlamı |
| --- | --- |
| `passed` | Beklenen dönüş kodu, aşılmamış bütçe ve tamamlanan temizlik |
| `failed` | Beklenmeyen çıkış/sinyal, süre aşımı, eksik veri, çıktı sınırı veya temizlik gerektiren canlı grup |
| `error` | Başlatma/kurulum veya kaynak temizleme hatası |

Ana süreç 0 döndürse bile canlı çocuk bırakırsa sonuç başarılı değildir.
Senaryo içindeki istisna temizlikten sonra korunur. Temizlik hatası ayrıca
`CleanupError` ve `cleanup_errors` ile görünür olur.

`process.json`: argv/cwd, PID/PGID, procfs grup kimliği, zamanlar, gerçek dönüş
kodu, sinyal, olaylar, bayt sayıları ve temizlik kanıtlarını içerir. Her kanalın
ham `<channel>.log` dosyası bulunur. Başlatma başarısızlığında olmayan süreç için
PID `null` kalır; hayalî bir başarılı çalışma yazılmaz.

## Gerçek kontroller

`tests/host/test_process.py` içindeki 17 kontrol:

| Kontrol | Gözlem |
| --- | --- |
| Normal/istenen kapanış | İki kanalın baytları ve SIGTERM handler'ının 0 ile kapanışı |
| Çıkış/sinyal | Hata kodu 7 ve negatif SIGUSR1 kodu korunur |
| Başlatma hatası | Olmayan executable, kapalı selector ve geri alınmış subreaper |
| Parçalı hazırlık | İki ayrı yazımda gelen NUL içeren işaret |
| Yarım kurulum | Süreç açıldıktan sonra geçersiz okuyucu, yine de toplanan grup |
| Yoğun çift yönlü I/O | 256 KiB giriş/echo ve pipe kapasitesini aşan stderr; kilitlenme yok |
| Hazırlık/EOF | Hazırlık süresinin dolması ile erken EOF ayrı kayıt |
| Çalışma süresi | Takılan sürecin sonlandırılması; sonuç başarısız kalır |
| Yazma süresi | Stdin okumayan hedefte dolan pipe ve sonlu yazma beklemesi |
| SIGTERM'i yok sayma | SIGKILL'e geçiş ve gerçek `-9` dönüş kodu |
| Çocuk ağacı | Parent ve fork edilmiş çocuğun kapatılıp toplanması |
| Erken parent çıkışı | 0 dönen parent'ın bıraktığı çocuk nedeniyle başarısız sonuç |
| Senaryo istisnası | İstisna sırasında da grup temizliği |
| Gerçek C seri uygulaması | İki PTY, iki yönde NUL içeren baytlar, Ctrl+C, fd sahipliği |
| Çıktı sınırı | 4096 bayt sınırında kesilme; sessiz başarı yok |
| İki grup | Bir grubun kapanması diğerini durdurmaz |
| Tekrarlı kaynak kullanımı | 10 çalıştırma sonunda açık fd kümesi aynı |

WP-02'nin 5 regresyonu da yeni süreç modülüyle geçti. Altı gerçek C/C++ hedefin
Make çağrıları aynı modüle bağlandı. WP-01'in eski deney araçları tarihsel referans
olarak korunur; bütün CAN senaryoları yeni modüle taşınmış gibi gösterilmez.

## Dayanaklar

- [Python subprocess — süreç ve dönüş kodları](https://docs.python.org/3/library/subprocess.html)
- [Linux child-subreaper — yetim çocukların alınması](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html)

Bu API belgeleri araç davranışının dayanağıdır; yukarıdaki başarı iddiaları
paketteki gerçek günlük ve süreç kayıtlarına dayanır.
