# WP-08 — doğrulanan Gemstone SDK ile ARM64 derleme

Bu paket, altı özgün C/C++ örneğinin Gemstone SDK'sı ile AArch64 Linux için
derlenebildiğini kanıtlar. Çalışma modu `cross_build_only` olarak kaydedilir.
Hedef programları native veya ARM emülatöründe çalıştırılmaz; O1 kartında
çalışma ve fiziksel CAN/UART kabulü ayrı işlerdir.

## Kaynak ve sabit kimlik

Resmî [toolchains deposunun v1.0.6 yayını](https://github.com/t3gemstone/toolchains/releases/tag/v1.0.6)
kullanılır. Yayın API'sinin seçilen varlık kaydı
`artifacts/wp08-toolchain/official-release.json` içinde korunur.
`latest` veya değişken bir indirme adresi kullanılmaz.

| Alan | Sabit değer |
| --- | --- |
| Arşiv | `t3gemstone-toolchains-ubuntu-jammy-minimal.tar.gz` |
| Yayın | `v1.0.6` |
| Boyut | 298.905.352 bayt |
| SHA-256 | `cd53ee3604329f75ac3fbd476467738d738a3ce92c0c91df9d6d9414f4d09a23` |
| Çalıştığı host | Linux x86_64 |
| GCC/G++ sürümü | 11.2.1 |
| Hedef üçlüsü | `aarch64-none-linux-gnu` |
| Sysroot | SDK'nın Ubuntu Jammy sysroot'u |
| Kurulum girdileri | 9.712 dosya ve sembolik bağlantı |
| Kurulu ağaç SHA-256 | `841cb555e7fc2b33fd5c38c6d788a3037328ce6295c24d7c62abd466f0d2f975` |

Yetkili yapılandırma `tests/toolchain.lock.json` dosyasıdır. Kurulum ağacı özeti,
doğrulanan arşivin dosyalarından doğrudan hesaplanıp temiz açılmış ağaçla
karşılaştırıldı. Her düzenli dosyanın yolu, içerik SHA-256'sı, boyutu ve
çalıştırılabilir biti; bağlantıların yolu ve hedefi sıralanmış JSON kayıtlarında
özetlenir. Hard link'ler dosya içerikleriyle temsil edilir. Kurulumun kendi iki
makbuz dosyası bu özetten hariçtir; makbuz değiştirmek kilidi değiştirmez.
Boş dizinler ve dosya zamanları içerik kimliğine katılmaz.

## Kurulum ve profil akışı

1. Yerel arşivi veya sabit yayın adresinden indirilen dosyayı boyut ve SHA-256
   ile doğrula. Uyumsuz dosya için kurulum dizinini oluşturma.
2. Yeni dizine Python 3.12'nin `tarfile.data_filter` filtresiyle aç. Yol taşması,
   dışarı yönelen bağlantı, özel dosya ve tekrarlanan arşiv yollarını reddet.
3. SDK sysroot'undaki iki mutlak SSL bağlantısını kilitteki göreli hedefe çevir.
   `/etc/ssl/certs` ve `/etc/ssl/private`, host'un `/etc` dizinine gitmez;
   kurulu SDK'nın `sysroot/etc/ssl/...` konumunda kalır. Başka bir dönüşüm
   kilitte açıkça tanımlanmadıkça kabul edilmez. Dosya içerikleri değiştirilmez.
4. Kurulu ağacı kilitle karşılaştır, kurulum makbuzunu ve dosya listesini yaz.
   Var olan dizinin üstüne yazma. Açma sırasında hata olursa yalnız bu
   kurulumun oluşturduğu dizini temizle.
5. Derlemeden önce ağacın tamamını yeniden denetle. Sonra doğrulanan `env`
   dosyasını ayrı bir Bash sürecinde yükle ve seçili SDK değişkenlerini al.
   Çağıran kabuğun ortamı değiştirilmez.
6. Derleyicilerin SDK içinde çözüldüğünü; `-dumpmachine`, `-dumpfullversion`
   ve `--print-sysroot` çıktılarının kilide uyduğunu doğrula.
7. Güncel kaynakları kendi alt Makefile'larıyla, `PROJDIR`, `BUILDDIR`, `CC`
   veya `CXX` parametreleriyle derle. Host ve AArch64 dizinlerini ayır.
8. ELF yapısını ve SDK `readelf` çıktısını doğrula. Kaynağı ve SDK ağacını
   işlem sonunda tekrar denetle. Değişiklik varsa çalışmayı başarılı gösterme.

Kaynak dosyaları upstream sürümüne sıfırlanmaz. Değiştirilmiş çalışma ağacı
olduğu gibi derlenir; referans commit ile farkları rapora yazılır.
Özgün upstream'deki 27 dosya bu teslimde değişmedi.

## Kullanım

Proje kökünde Linux x86_64, Python 3.12+, Bash ve GNU Make gerekir. Native
kontroller ayrıca GCC/G++, Git ve `tests/requirements.txt` bağımlılıklarını
kullanır. SDK kurulum kodunun ek Python bağımlılığı yoktur.

```sh
python3 -m tests.testlab toolchain --output build/gemstone-sdk
python3 -m tests.testlab build --profile aarch64 --toolchain-root build/gemstone-sdk
python3 -m tests.testlab build --profile host
```

Önceden indirilmiş aynı arşivle:

```sh
python3 -m tests.testlab toolchain --archive /tam/yol/t3gemstone-toolchains-ubuntu-jammy-minimal.tar.gz --output build/gemstone-sdk
```

`--output` yeni bir dizin olmalıdır. SDK dizini boşluk içerebilir; C ve C++
ile gerçek derleme üzerinden doğrulandı. Kaynak ve build dizinleri, özgün
Makefile'ların yol kuralları nedeniyle boşluksuz seçilmelidir. SDK'nın `env`
dosyası değiştirilmez; compiler argümanları ve sysroot içeren Make bayrakları
profilde uygun şekilde tırnaklanır.

Host profilindeki `--cc/--cxx` mevcut işlevini korur. AArch64 profilinde
derleyici geçersiz kılma kabul edilmez. Eksik/değişmiş SDK durumunda host GCC
ile devam edilmez. `MAKEFLAGS`, `MAKEFILES`, compiler flags ve compiler/header/
library arama yolları gibi dış ayarlar temizlenir. SDK'nın `CFLAGS`, `CXXFLAGS`
ve `LDFLAGS` değerleri alınır; özgün `common.mk` uyarıları bunlara eklenir.
Derleme günlüklerinde `-Wall`, `-Wextra`, `-Werror`, C11 ve C++17 bayrakları
görünür. Uyarılar bastırılarak başarılı sonuç elde edilmez.

Çıkış kodları: başarılı derleme `0`, Make/ELF kabul hatası `1`, SDK/araç/
girdi hatası `2`. Kaynak veya SDK'nın çalışma sırasında değişmesi altyapı
hatasıdır. Her denemenin yeni run/build dizini vardır; önceki binary tekrar
başarılı çıktı olarak kullanılamaz.

## Üretilen kanıtlar

`run.json`, mevcut build raporu sürüm 1'i `profile: aarch64` ile kullanır.
Pytest'in `testlab.run` raporu ayrı bir rapor türüdür. Build raporu şu bilgileri
içerir:

- Kilitli yayın/arşiv, SDK'nın işlem öncesi/sonrası dosya özeti ve sysroot.
- Kaynak içerikleri, referans commit farkı ve varsa gerçek Git/dirty durumu.
- Derleyici sürümleri, gerçek argv, kaldırılan dış değişkenler ve SDK bayrakları.
- Her binary'nin SHA-256'sı, boyutu, ELF sınıfı, mimarisi, yükleme segmentleri
  ve program yükleyicisi.
- `readelf -h -l -d -V` günlüğü, `DT_NEEDED` kütüphaneleri ve gereken
  GLIBC/GLIBCXX/CXXABI sembol sürümleri.
- `commands.jsonl` ve her yardımcı süreç için süre, gerçek dönüş kodu ve
  grup/pipe temizliği kaydı.

Altı hedefin tümü ELF64, little-endian, `e_machine=183` ve
`/lib/ld-linux-aarch64.so.1` yükleyicisiyle üretildi. C hedeflerinde `libc.so.6`;
C++ hedeflerinde ayrıca `libstdc++.so.6` ve `libgcc_s.so.1` görüldü.
Çıktılar `GLIBC_2.34` dahil sürümlü semboller gerektiriyor. Kartın dosya
sisteminin bu ABI'yi sağladığı bu aşamada denenmedi.

Başarılı raporda da `host_runtime: not_run`, `board_runtime: not_run` ve
`github_hosted_runner: not_executed` kalır; yalnız `arm64_build: passed`
olur. Derleme doğrulaması, gerçek zamanlılık veya sürücü kabulü değildir.
Debug yolları nedeniyle binary'ler için bit düzeyinde tekrarlanabilirlik
iddiası yapılmaz.

## Gerçek kontroller ve kabul

```sh
python3 tools/check_cross_build.py --toolchain-root build/gemstone-sdk --output artifacts/cross-check
```

Kontrol, çağıranın kaynaklarını ve SDK'sını korur. SDK taşıma/tahrif deneyinde
geçici alanda yaklaşık 1 GB ayrı kopya oluşturur, sonra kaldırır.

| Kontrol | Gözlenen sonuç |
| --- | --- |
| Altı özgün hedef | 6/6 AArch64 ELF geçti |
| Bozuk dış CC/CFLAGS/LDFLAGS/MAKEFLAGS ve arama yolları | Altı hedef geçti; üst süreç ortamı değişmedi |
| Özel C kaynağına gerçek `#error` eklenmesi | CLI 1, binary yok; sağlıklı seri hedefi geçti; eski binary kullanılmadı |
| Boşluk içeren başka SDK dizini | C ve C++ hedefi geçti; aynı kurulum özeti |
| Ayrı SDK kopyasının `env` içeriğinin değiştirilmesi | CLI 2; `env` yüklenmedi, derleyici başlamadı, host'a düşülmedi |
| Küçük gerçek tar fixture'ları | Yanlış boyut/hash, yol taşması, dış bağlantı ve var olan dizin koruması geçti |
| Kurulu fixture değişimleri | İçerik, çalıştırma biti, ekleme, silme ve bağlantı değişimleri yakalandı |
| Yanlış mimari/kesik ELF, eksik SDK, compiler override | Reddedildi |
| Native/host/seri regresyonu | 6/6 native, 54/54 host, 45/45 seri geçti |

Son seri kabulü önerilen dört yamanın özel kaynak kopyasına aittir. Özgün seri
kusurlarının düzeltildiği iddia edilmez. Bu paket vcan'ın uzun tam takımını
yeniden çalıştırmadı; önceki WP-07'deki 36 gerçek vcan kabulü tarihsel kanıt
olarak korunur. Güncel harness ile kontrollü seri hatasının yeniden üretimi
ve temiz ZIP kabulü ayrıca kaydedilir.

| Dizin | İçerik |
| --- | --- |
| `artifacts/wp08-toolchain/` | Resmî yayın kimliği, kurulum makbuzu, kurulu dosya listesi |
| `artifacts/wp08-cross-builds/` | Altı özgün ARM64 derleme |
| `artifacts/wp08-controlled-builds/` | İlk taşıma denemesinde yakalanan LDFLAGS hatası; kabul değildir |
| `artifacts/wp08-controlled-final/` | Düzeltilmiş kodla dört gerçek kontrolün kabulü |
| `artifacts/wp08-native-builds/` | Altı özgün host derleme |
| `artifacts/wp08-host-final/`, `artifacts/wp08-serial-final/` | Güncel test/JUnit/temizlik kanıtları |
| `artifacts/wp08-reproduction/` | Güncel harness ile gerçek seri hata tekrarı |
| `artifacts/wp08-clean-room/` | Paketten yeniden kurulum/derleme ve test kanıtları |

SDK arşivi, SDK binary'leri ve üretilmiş uygulama binary'leri teslim ZIP'ine
konmaz. Kilit, kurulum listeleri ve süreç/readelf günlükleriyle yeniden
üretilebilirler. Kaynak paketi SDK indirmesini ve doğrulamasını araçlara bırakır.

## CI ve sonraki paket

`aarch64-cross-build` GitHub Actions işi, Ubuntu 24.04 üzerinde sabit SDK'yı
kurup altı hedefi derlemek ve kanıtları saklamak için eklendi. Bu YAML yerel
olarak incelendi; gerçek hosted runner çalışması yapılmadı.
WP-09'da dört profil için uzak run URL'si ve yüklenmiş kanıtlarla kabul kapanır.
