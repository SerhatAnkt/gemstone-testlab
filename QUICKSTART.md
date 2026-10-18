# Temiz kurulum ve ilk çalıştırma

Bu kılavuz `Gemstone_TestLab_Source.zip` açıldığında veya TestLab kaynak
deposunun kökünde uygulanır. Referans ortam **Ubuntu 24.04 x86_64, Python 3.12**.
Kart gerekmez. Aşağıdaki komutların tümü proje kökünde çalıştırılır.
`python3 --version` çıktısı 3.12 olmalıdır; CI bağımlılıkları bu sürüme kilitlidir.

## 1. Sistem ve Python bağımlılıkları

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends -y build-essential python3 python3-venv git iproute2 kmod sudo ca-certificates
python3 -m venv .venv-testlab
.venv-testlab/bin/python -m pip install --require-hashes -r tests/requirements-serial.txt
```

Seri requirements dosyası host/CAN bağımlılıklarını da içerir. Paket sürümleri
ve wheel SHA-256 değerleri `tests/*dependencies.lock.json` içindedir. İlk kurulum
internet kullanır. Önceden hazırlanmış wheel diziniyle aynı kontrol çevrimdışı
yapılabilir: pip komutuna `--no-index --find-links /tam/yol/wheels` eklenir.
Wheel ve SDK dosyaları kaynak arşivinin parçası değildir.

## 2. Önce ayrıcalıksız profiller

```sh
.venv-testlab/bin/python -m tests.testlab ci --profile host --output artifacts/first-host
.venv-testlab/bin/python -m tests.testlab ci --profile serial --source-profile proposed-fixes --output artifacts/first-serial
```

Beklenen: host **66 vaka + altı native derleme**, seri **45 vaka + iki native
derleme**, her komutta çıkış 0. İkinci komut dört seri düzeltmesini özel kopyaya
uygular. Özgün `upstream/examples` değişmez. `--source-profile working-tree`
seçilirse özgün seri sürümdeki 11 regresyonun başarısız olması beklenir.

**Her çalıştırmada yeni çıktı adı kullanılır.** Araç eski raporu yeniden
kullanmaz ve var olan dizinin üzerine yazmaz. Çıktıda `ci.json`, `junit.xml`,
ham komut günlükleri ve kaynak özetleri bulunur. Hata kodunu görmek için komutun
hemen ardından `echo $?` çalıştırılabilir. `tee` kullanılıyorsa gerçek komutun
çıkış kodunu korumak gerekir.

## 3. SDK'yı bir defa kur

```sh
python3 -m tests.testlab toolchain --output build/gemstone-sdk
```

Bu komut resmî v1.0.6 SDK'sının yaklaşık 299 MB arşivini indirir, boyut/SHA-256
kontrolünden sonra yeni dizine açar. Açılmış SDK ve derlemeler için birkaç GB
boş alan ayırın. Yerel kilitli arşiv varsa `--archive /tam/yol/arsiv.tar.gz`
eklenebilir. Mevcut SDK dizinine ikinci kez kurulum yapılmaz; sonraki testler
aynı doğrulanmış dizini `--toolchain-root` ile kullanır.

## 4. CAN önkoşulunu hazırla

Tam native kabul **normal kullanıcıyla** başlatılır. Yalnızca çekirdek modülü
ve geçici arayüz işlemleri `sudo -n` ile yapılır. Runner/VM yöneticisi bu kullanıcı
için gerçek `ip` ve `modprobe` yollarını ve yetki kapsamını yapılandırmalıdır.
Yerel geliştirmede `sudo -v` ile açılmış geçerli sudo oturumu da kullanılabilir;
bu oturumun süresi tam koşu boyunca yeterli olmalıdır. Aracı bütünüyle `sudo`
ile çalıştırmayın.

```sh
sudo -v
sudo -n modprobe vcan
sudo -n ip -details -json link show
```

Son komutun başarısı arayüz oluşturma yetkisini tek başına kanıtlamaz. Gerçek
fixture kendi benzersiz `gtl...` arayüzünü oluşturup kimliğini doğrular ve
temizler. Önceden `vcan0` oluşturmanız gerekmez. `Module vcan not found` veya
`Operation not permitted` alınırsa çekirdek modülü ve ağ yetkisi düzeltilmelidir.
Root olmak, konteynerde bu yetkinin bulunduğu anlamına gelmez.

## 5. Zorunlu dört profili tek komutla çalıştır

İlk kurulum ve CAN yetkisi hazırlandıktan sonra:

```sh
.venv-testlab/bin/python tools/run_release.py --source-profile proposed-fixes --toolchain-root build/gemstone-sdk --output artifacts/release-first
```

Araç host → seri → CAN → AArch64 profillerini başlatır, ardından dört raporu
`ci-verify` ile birleştirir. Bir profil başarısız olduğunda diğer profillerin
kanıtı da toplanır. Hiçbir profil isteğe bağlı değildir; eksik SDK, eksik CAN
yetkisi, boş/atlanmış test veya değişmiş kanıt tam kabul vermez.

| Çıktı | Anlam |
| --- | --- |
| `release.json` | Dört başlatıcının gerçek kodu, toplam durum ve hata |
| `acceptance.json` | Dört profilin kaynak/harness/commit ve kanıt tutarlılığı |
| `host/`, `serial/`, `can/`, `aarch64/` | Profillerin `ci.json` ve ayrıntılı kanıtı |
| `launchers/` | Başlatıcı süreçlerinin stdout/stderr, zaman aşımı ve temizliği |

Çıkış `0`: tüm profiller ve toplam denetim geçti. `1`: test/derleme/kabul
başarısızlığı. `2`: önkoşul veya altyapı hatası. AArch64 sonucu yalnızca
çapraz derlemedir; ARM64 programları ve O1 kartı çalıştırılmaz. Yerel kabul
GitHub Actions koşusu olarak gösterilmez.

## Host CAN yetkisi vermiyorsa

Önce [VM_REPRODUCTION.md](docs/VM_REPRODUCTION.md) ile ayrı x86 Linux runtime'ı
ve kilitli pytest wheel dizini hazırlanır. Bu ağır runtime kaynak paketine
eklenmez. Hazırlanan mutlak yollar verilerek aynı zorunlu dört profil şöyle
başlatılır:

```sh
.venv-testlab/bin/python tools/run_release.py --source-profile proposed-fixes --toolchain-root build/gemstone-sdk --can-backend vm --guest-root /tam/yol/guest-root --wheels /tam/yol/wheels --profile-timeout 1200 --output artifacts/release-vm-first
```

`/tam/yol/...` alanları kendi hazırladığınız gerçek dizinlerle değiştirilir.
Bu yol **Git metadatası olmayan kaynak ZIP'inden** çalışır. Mevcut VM adapter'ı
checkout kimliğini konuğa taşımadığından Git checkout'u içindeki toplam VM
kabulü reddedilir; checkout kimliğiyle kabul için native CAN veya GitHub
workflow'u kullanılır. Ayrı VM UID 1000 ile gerçek SocketCAN/vcan testlerini
çalıştırır. ARM/O1 emülasyonu değildir. VM'nin CI kanıtı
`can/guest-artifacts/ci-can/ci.json` içindedir.
TCG'nin toplam çalışma süresi host yüküne bağlıdır. Bu örnekte toplam profil
bütçesi 1.200 saniyedir; vakaların mevcut `timeout-scale=4` değeri değişmez.
WP-10 temiz kabulü 600 saniyelik toplam bütçede geçti, ancak bu sınırın yakınına
geldi; bu nedenle yavaş ortamlar için örnekte daha geniş dış bütçe seçildi.

## Hata, katkı ve dağıtım

Test çıktısındaki `TestLab reproduce:` komutu ilgili `failure.json` dosyasından
aynı vakayı tekrarlar. Eski bir teslimin hata raporu yeni harness ile
uyuşmuyorsa reddedilir; aynı kaynak teslimi kullanılmalıdır. Ayrıntılar:
[WP07_REPORTING.md](docs/WP07_REPORTING.md).

Beş düzeltmenin bağımsız kontrolü ve PR sırası:
[CONTRIBUTING.md](CONTRIBUTING.md). Kaynak ZIP'ini yeniden üretmek/doğrulamak:

```sh
python3 tools/export_source.py --output dist/Gemstone_TestLab_Source.zip
python3 tools/export_source.py --verify dist/Gemstone_TestLab_Source.zip
```

Kaynak paketi test kodunu, kılavuzları, yamaları ve 27 özgün upstream dosyasını
içerir. Geçmiş ham kanıtlar yalnızca tam `Gemstone_TestLab.zip` teslimindedir;
eski kanıt yollarını kaynak ZIP'inde aramayın. Kaynak ZIP'inin
`RELEASE_MANIFEST.json` dosyası tüm paket dosyalarının SHA-256/boyut/mode
listesini içerir; imzalı bir yayın veya uzak runner tasdiki değildir.
