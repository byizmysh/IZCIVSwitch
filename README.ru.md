# IZCIVSwitch — IZlauncher Edition (RU)

Краткая русская инструкция. Полная английская версия: [`README.md`](README.md).

**Проверено на железе:** `verified: True`, 26/26 стадий, retained FS endpoint,
319 496 RPC exchanges, `switch2-nTDhp6`.

## Установка (сначала это)

### 1. Распаковать

Распаковать **весь** архив в папку, доступную для записи. Не запускать из
внутри архива.

```
IZCIVSwitch-0.1.0/
├── IZCIVSwitch.py
├── pc-install-trigger.py
├── kit/
├── panel/
├── izlauncher/
└── README.md
```

### 2. Положить `prod.keys`

`prod.keys` **не входит** в релиз. Он нужен только для Lobby-инъекции
(`IZCIVSwitch.py --lobby` и `pc-install-trigger.py`).

Положить свой дамп ровно сюда:

```
panel/data/private/civswitchldn/prod.keys
```

```bash
chmod 700 panel/data/private/civswitchldn
chmod 600 panel/data/private/civswitchldn/prod.keys
```

В файле должны быть минимум:

```
aes_kek_generation_source
aes_key_generation_source
master_key_00
master_key_12
```

Это стандартный текстовый `prod.keys` с твоей консоли. `title.keys` не нужен.
Никогда не коммитить и не публиковать.

Если ключей нет — использовать Switch 1 NRO из оригинального kit для установки
`XSTRIG.Civ7Save`, затем `IZCIVSwitch.py --no-lobby` (ключи не нужны).

### 3. Вернуть capabilities

```bash
sudo setcap cap_net_admin,cap_net_raw=ep \
  panel/data/runtime/civswitchldn/bin/python-ldn
getcap panel/data/runtime/civswitchldn/bin/python-ldn
```

Ожидается: `cap_net_admin,cap_net_raw=ep`.

Полный архив — Linux x86_64 и runtime Python 3.14. На другой системе
использовать свой `iz2s-panel` через `--panel` или Switch 1 NRO.

### 4. Проверить

```bash
python3 pc-install-trigger.py --check
```

Ожидается:

```
panel : .../panel
kit   : .../kit
radio : phyN
[ok] LDN environment is ready
```

### 5. Запустить

S2: Civ7 → `MULTIPLAYER > WIRELESS > CREATE GAME > HOST LOBBY`.

ПК:

```bash
python3 IZCIVSwitch.py --lobby --yes
```

Успех:

```
4/4 verified
FS ENDPOINT IS LIVE
```

`Ctrl-C` освобождает endpoint и делает cleanup.

## Persistent: XSTRIG + Load Game

Один раз, пока S2 в лобби:

```bash
python3 pc-install-trigger.py --yes
```

Затем:

1. питание 12 секунд;
2. Civ7 → `Load Game` → `XSTRIG.Civ7Save`;
3. дождаться `Awaiting payload at <IP>:9026`;
4. `python3 IZCIVSwitch.py --no-lobby`.

## Опционально: меню 0.27

```bash
python3 izlauncher/install.py --ip <S2-IP>
```

После `INSTALL DONE`: reboot → `Load Game` → `IZ2S.Civ7Save` → меню →
дважды **R3** → `python3 IZCIVSwitch.py --no-lobby`.

## Диагностика

| Симптом | Что делать |
|---|---|
| `prod.keys not ready` | Проверить путь и обязательные ключи. |
| `capabilitiesReady: false` | Повторить `setcap`. |
| `radio phyN is absent` | Переподключить USB Wi-Fi; `--phy`. |
| `loader did not answer` | S2 не в лобби или сменился IP; `--console-ip`. |
| `Got unstable rw primitive` / `604:48` / `657:28` | JS-эксплойт не поднялся; hard reset. |
| `FS acquisition did not complete` | Вероятностный промах; hard reset. |
| `2/4`, `idle` растёт | Wedge; питание 12 с. |
| `rpc.cjs status` → `ECONNREFUSED` | Использовать `--inspect`. |

Подробности, опции и безопасность — в [`README.md`](README.md) и
[`DISCLAIMER.md`](DISCLAIMER.md).
