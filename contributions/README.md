# Upstream katkı paketleri

Referans: `t3gemstone/examples@2619a7584d39203a057abc08ab7c6698dc476868`.
**Durum: taslak; issue/PR gönderilmedi.** Her yama özgün sürüme bağımsız
uygulanır. Sayılar yalnız aşağıdaki odaklı regresyon seçimidir; tam matrisin
yerine geçmez. Toplam 12 kusurlu vaka, beş ayrı düzeltmeyle değerlendirilir.

| Giriş | Sorun | Yama | Odaklı vaka | PR açıklaması |
| --- | --- | --- | --- | --- |
| 01 | C CAN göndericisi başarısız indeks sorgusunu kullanıyor | `0001` | 1 | [01-can-interface.md](01-can-interface.md) |
| 02 | C/C++ seri RX, CR baytını LF'ye çeviriyor | `0002` | 4 | [02-serial-raw-input.md](02-serial-raw-input.md) |
| 03 | C/C++ `9600oops` baud değerini kabul ediyor | `0003` | 2 | [03-serial-baud.md](03-serial-baud.md) |
| 04 | Python toplu konsol girdisi tamponda kalıyor | `0004` | 3 | [04-python-stdin.md](04-python-stdin.md) |
| 05 | Python `--help` başarısız çıkış veriyor | `0005` | 2 | [05-python-help.md](05-python-help.md) |

Tam yama adları, değişmesi gereken dosyalar ve kesin pytest node'ları
[series.json](series.json) içindedir. `tools/check_contributions.py`, her giriş
için önce özgün sürümde gerçek call başarısızlığını, sonra yalnız o yamanın
kopyasında başarıyı ister. Tüm yamalar birlikte ayrıca tam CAN/seri CI
profillerinde sınanır. Komutlar ve gönderme adımları:
[CONTRIBUTING.md](../CONTRIBUTING.md).

PR dosyalarının İngilizce başlığı ve açıklaması gönderime uyarlanabilir.
Yerel kanıt adresleri uzak ek değildir; gönderimden önce gerçek kanıt eklenmeli
ve güncel upstream sürümünde yeniden doğrulanmalıdır.
