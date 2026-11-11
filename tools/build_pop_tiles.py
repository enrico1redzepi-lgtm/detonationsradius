"""Schneidet das GHSL-Bevölkerungsraster (WGS84, 30 Bogensekunden ≈ 1 km) in 1°×1°-Kacheln.

Jede Kachel: 120×120 Zellen, Uint16, kodiert als round(sqrt(Einwohner) * 100),
gzip-komprimiert. Kacheln ohne Einwohner werden nicht geschrieben.
Dateiname: data/pop/{lat}_{lon}.bin.gz mit lat/lon = Südwest-Ecke in ganzen Grad.
"""
import gzip, json, math, os, sys
import numpy as np
import rasterio
from rasterio.windows import Window

src_path, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
N = 120  # Zellen pro Grad
count, total_bytes, total_pop = 0, 0, 0.0
index = []
with rasterio.open(src_path) as src:
    print("Raster:", src.width, src.height, src.transform, src.dtypes, src.nodata, flush=True)
    t = src.transform
    x0, y0, res = t.c, t.f, t.a
    for lat_top in range(90, -60, -10):          # Blöcke von 10°×10°
        for lon_left in range(-180, 180, 10):
            col = round((lon_left - x0) / res); row = round((y0 - lat_top) / res)
            w = Window(col, row, 10 * N, 10 * N)
            block = src.read(1, window=w, boundless=True, fill_value=0).astype(np.float64)
            if src.nodata is not None:
                block[block == src.nodata] = 0
            block[~np.isfinite(block)] = 0
            block[block < 0] = 0
            if block.sum() < 1:
                continue
            for i in range(10):
                for j in range(10):
                    tile = block[i*N:(i+1)*N, j*N:(j+1)*N]
                    s = tile.sum()
                    if s < 1:
                        continue
                    enc = np.minimum(np.round(np.sqrt(tile) * 100), 65535).astype("<u2")
                    lat = lat_top - (i + 1); lon = lon_left + j
                    data = gzip.compress(enc.tobytes(), 9)
                    with open(os.path.join(out_dir, f"{lat}_{lon}.bin.gz"), "wb") as f:
                        f.write(data)
                    index.append([lat, lon])
                    count += 1; total_bytes += len(data); total_pop += s
        print(f"bis {lat_top-10}°: {count} Kacheln, {total_bytes/1e6:.1f} MB, {total_pop/1e9:.3f} Mrd. Einwohner", flush=True)
with open(os.path.join(out_dir, "index.json"), "w") as f:
    json.dump({"n": N, "enc": "sqrt100_u16_gz", "tiles": index}, f, separators=(",", ":"))
print("Fertig:", count, "Kacheln", f"{total_bytes/1e6:.1f} MB", f"{total_pop/1e9:.3f} Mrd. Einwohner")
