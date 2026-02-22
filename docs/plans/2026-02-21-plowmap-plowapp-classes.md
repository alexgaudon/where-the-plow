# PlowMap + PlowApp Class Refactor

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract scattered module-level state and map operations in `app.js` into two classes — `PlowMap` (map + all layers) and `PlowApp` (state + coordination) — to make state management obvious and prevent async race bugs.

**Architecture:** `PlowMap` wraps the maplibre instance and owns all add/remove/update layer operations. `PlowApp` owns mode state, coverage data, refresh timers, and active vehicle tracking — it calls `PlowMap` methods to update the map. Top-level code creates both instances and wires DOM event listeners that call into `PlowApp`. Stateless helpers (`vehicleColor`, `formatTimestamp`, `buildTrailSegments`, etc.) stay as plain functions.

**Tech Stack:** Vanilla JS (no build step), MapLibre GL JS

---

### Task 1: Create PlowMap class with constructor and passthrough methods

**Files:**
- Modify: `src/where_the_plow/static/app.js`

**Step 1: Write the PlowMap class skeleton**

Replace the current map init block (lines 11-26) and move the map construction into a class. Place the class definition right after the panel toggle code (line 9). The class wraps `maplibregl.Map` and exposes passthroughs.

```js
class PlowMap {
    constructor(container, options) {
        this.map = new maplibregl.Map({ container, ...options });
        this.coverageAbort = null;
    }

    on(event, layerOrCb, cb) {
        if (cb) this.map.on(event, layerOrCb, cb);
        else this.map.on(event, layerOrCb);
    }

    addControl(control, position) {
        this.map.addControl(control, position);
    }

    getZoom() { return this.map.getZoom(); }
    getCenter() { return this.map.getCenter(); }
    getBounds() { return this.map.getBounds(); }
    getCanvas() { return this.map.getCanvas(); }
}
```

**Step 2: Instantiate PlowMap and update all `map.` references that use passthroughs**

After the class, create the instance:
```js
const plowMap = new PlowMap("map", {
    style: "https://tiles.openfreemap.org/styles/liberty",
    center: [-52.71, 47.56],
    zoom: 12,
});
```

Update geolocate setup to use `plowMap.addControl(...)` and `plowMap.on(...)`.
Update viewport tracking to use `plowMap.getZoom()`, `plowMap.getCenter()`, `plowMap.getBounds()`.

**Step 3: Verify the app loads and map renders**

Run: `uv run cli.py dev` and check browser — map should render identically.

**Step 4: Commit**

```
refactor: add PlowMap class with constructor and passthroughs
```

---

### Task 2: Move vehicle layer management into PlowMap

**Files:**
- Modify: `src/where_the_plow/static/app.js`

**Step 1: Add vehicle methods to PlowMap**

```js
// Inside PlowMap class:

initVehicles(data) {
    this.map.addSource("vehicles", { type: "geojson", data });
    this.map.addLayer({
        id: "vehicle-circles",
        type: "circle",
        source: "vehicles",
        paint: {
            "circle-color": [
                "match", ["get", "vehicle_type"],
                "SA PLOW TRUCK", "#2563eb",
                "TA PLOW TRUCK", "#2563eb",
                "LOADER", "#ea580c",
                "GRADER", "#16a34a",
                "#6b7280",
            ],
            "circle-radius": 7,
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2,
        },
    });
}

updateVehicles(data) {
    this.map.getSource("vehicles").setData(data);
}

setVehiclesVisible(visible) {
    if (this.map.getLayer("vehicle-circles")) {
        this.map.setLayoutProperty(
            "vehicle-circles", "visibility", visible ? "visible" : "none"
        );
    }
}
```

**Step 2: Update map load handler and enterRealtime/enterCoverage**

Replace direct `map.addSource("vehicles", ...)` / `map.addLayer(...)` with `plowMap.initVehicles(data)`.
Replace `map.getSource("vehicles").setData(...)` with `plowMap.updateVehicles(data)`.
Replace `map.setLayoutProperty("vehicle-circles", ...)` calls with `plowMap.setVehiclesVisible(bool)`.

**Step 3: Verify — map loads, vehicles appear, mode switching hides/shows them**

**Step 4: Commit**

```
refactor: move vehicle layer management into PlowMap
```

---

### Task 3: Move trail layer management into PlowMap

**Files:**
- Modify: `src/where_the_plow/static/app.js`

**Step 1: Add trail methods to PlowMap**

```js
// Inside PlowMap class:

showTrail(trailData, lineData) {
    this.clearTrail();
    this.map.addSource("vehicle-trail", { type: "geojson", data: trailData });
    this.map.addSource("vehicle-trail-line", { type: "geojson", data: lineData });

    this.map.addLayer({
        id: "vehicle-trail-line",
        type: "line",
        source: "vehicle-trail-line",
        paint: {
            "line-color": "#60a5fa",
            "line-width": 3,
            "line-opacity": ["get", "seg_opacity"],
        },
    }, "vehicle-circles");

    this.map.addLayer({
        id: "vehicle-trail-dots",
        type: "circle",
        source: "vehicle-trail",
        paint: {
            "circle-color": "#60a5fa",
            "circle-radius": 4,
            "circle-opacity": ["get", "trail_opacity"],
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1,
            "circle-stroke-opacity": ["*", ["get", "trail_opacity"], 0.8],
        },
    }, "vehicle-circles");
}

updateTrail(trailData, lineData) {
    const trailSource = this.map.getSource("vehicle-trail");
    if (trailSource) trailSource.setData(trailData);
    const lineSource = this.map.getSource("vehicle-trail-line");
    if (lineSource) lineSource.setData(lineData);
}

clearTrail() {
    if (this.map.getLayer("vehicle-trail-dots")) this.map.removeLayer("vehicle-trail-dots");
    if (this.map.getLayer("vehicle-trail-line")) this.map.removeLayer("vehicle-trail-line");
    if (this.map.getSource("vehicle-trail")) this.map.removeSource("vehicle-trail");
    if (this.map.getSource("vehicle-trail-line")) this.map.removeSource("vehicle-trail-line");
}
```

**Step 2: Update showTrail, refreshTrail, clearTrail callers**

The top-level `showTrail()` function should prepare data and call `plowMap.showTrail(trailData, lineData)`.
`refreshTrail()` should call `plowMap.updateTrail(trailData, lineData)`.
`closeDetail()` should call `plowMap.clearTrail()`.

**Step 3: Verify — click a vehicle, trail appears, close detail clears it**

**Step 4: Commit**

```
refactor: move trail layer management into PlowMap
```

---

### Task 4: Move coverage layer management into PlowMap

**Files:**
- Modify: `src/where_the_plow/static/app.js`

**Step 1: Add coverage methods to PlowMap**

```js
// Inside PlowMap class:

renderCoverageLines(segmentData) {
    const source = this.map.getSource("coverage-lines");
    if (source) {
        source.setData(segmentData);
    } else {
        this.map.addSource("coverage-lines", { type: "geojson", data: segmentData });
        this.map.addLayer({
            id: "coverage-lines",
            type: "line",
            source: "coverage-lines",
            paint: {
                "line-color": ["get", "seg_color"],
                "line-width": 3,
                "line-opacity": ["get", "seg_opacity"],
            },
        });
    }
}

renderHeatmap(pointData) {
    const source = this.map.getSource("coverage-heatmap");
    if (source) {
        source.setData(pointData);
    } else {
        this.map.addSource("coverage-heatmap", { type: "geojson", data: pointData });
        this.map.addLayer({
            id: "coverage-heatmap",
            type: "heatmap",
            source: "coverage-heatmap",
            paint: {
                "heatmap-weight": 0.5,
                "heatmap-intensity": [
                    "interpolate", ["linear"], ["zoom"],
                    10, 0.5, 12, 1, 15, 2,
                ],
                "heatmap-radius": [
                    "interpolate", ["linear"], ["zoom"],
                    10, 3, 12, 8, 14, 15, 16, 25,
                ],
                "heatmap-opacity": 0.75,
                "heatmap-color": [
                    "interpolate", ["linear"], ["heatmap-density"],
                    0, "rgba(0,0,0,0)",
                    0.15, "#2563eb",
                    0.35, "#60a5fa",
                    0.55, "#fbbf24",
                    0.75, "#f97316",
                    1.0, "#ef4444",
                ],
            },
        });
    }
}

setCoverageLineVisibility(visible) {
    if (this.map.getLayer("coverage-lines")) {
        this.map.setLayoutProperty("coverage-lines", "visibility", visible ? "visible" : "none");
    }
}

setHeatmapVisibility(visible) {
    if (this.map.getLayer("coverage-heatmap")) {
        this.map.setLayoutProperty("coverage-heatmap", "visibility", visible ? "visible" : "none");
    }
}

clearCoverage() {
    if (this.map.getLayer("coverage-lines")) this.map.removeLayer("coverage-lines");
    if (this.map.getSource("coverage-lines")) this.map.removeSource("coverage-lines");
    if (this.map.getLayer("coverage-heatmap")) this.map.removeLayer("coverage-heatmap");
    if (this.map.getSource("coverage-heatmap")) this.map.removeSource("coverage-heatmap");
}
```

**Step 2: Add abort management to PlowMap**

```js
// Inside PlowMap class:

abortCoverage() {
    if (this.coverageAbort) {
        this.coverageAbort.abort();
        this.coverageAbort = null;
    }
}

newCoverageSignal() {
    this.abortCoverage();
    this.coverageAbort = new AbortController();
    return this.coverageAbort.signal;
}
```

**Step 3: Update all callers**

Replace `clearCoverageLayers()` / `clearHeatmapLayer()` calls with `plowMap.clearCoverage()`.
Replace inline `renderCoverageLines` / `renderHeatmap` with calls to `plowMap.renderCoverageLines(data)` / `plowMap.renderHeatmap(data)`.
Replace visibility toggles with `plowMap.setCoverageLineVisibility(bool)` / `plowMap.setHeatmapVisibility(bool)`.
Replace abort controller logic with `plowMap.abortCoverage()` / `plowMap.newCoverageSignal()`.
Remove the old standalone `clearCoverageLayers()`, `clearHeatmapLayer()` functions.

**Step 4: Verify — coverage mode works, lines/heatmap toggle, slider, mode switching clears layers**

**Step 5: Commit**

```
refactor: move coverage layer management into PlowMap
```

---

### Task 5: Create PlowApp class and move state into it

**Files:**
- Modify: `src/where_the_plow/static/app.js`

**Step 1: Write PlowApp class with constructor**

Place after PlowMap instantiation. Move all module-level `let` state variables into the constructor.

```js
class PlowApp {
    constructor(plowMap) {
        this.map = plowMap;

        // Mode
        this.mode = "realtime";

        // Realtime
        this.refreshInterval = null;
        this.activeVehicleId = null;
        this.activeVehicleTimestamp = null;

        // Coverage
        this.coverageData = null;
        this.coverageSince = null;
        this.coverageUntil = null;
        this.coveragePreset = "24";
        this.coverageView = "lines";
    }
}
```

**Step 2: Move mode switching methods into PlowApp**

Move `switchMode`, `enterRealtime`, `enterCoverage` into the class. Update references from module-level variables (`currentMode`, `coverageData`, etc.) to `this.mode`, `this.coverageData`, etc.

**Step 3: Move coverage methods into PlowApp**

Move `loadCoverageForRange`, `loadCoverageForDate`, `renderCoverage`, `switchCoverageView`, `sliderToTime` into the class. The data-preparation logic (segment building, point extraction) stays inside these methods — they call `this.map.renderCoverageLines(data)` etc.

**Step 4: Move auto-refresh methods into PlowApp**

Move `startAutoRefresh`, `stopAutoRefresh` into the class. The refresh callback calls `this.map.updateVehicles(data)`.

**Step 5: Move vehicle detail methods into PlowApp**

Move `showVehicleDetail` (was `showDetail`), `closeVehicleDetail` (was `closeDetail`), `updateDetailFromData`, `showTrail`, `refreshTrail` into the class. Trail data prep (`addTrailOpacity`, `buildTrailSegments`) stays as plain functions — `showTrail` calls them then passes results to `this.map.showTrail(trailData, lineData)`.

**Step 6: Instantiate PlowApp and update event wiring**

```js
const app = new PlowApp(plowMap);
```

Update all DOM event listeners to call `app.switchMode(...)`, `app.loadCoverageForRange(...)`, etc.
Update `plowMap.on("load", ...)` to call `app.startAutoRefresh()`.
Remove all module-level `let` state variables.

**Step 7: Verify — full functionality test**

- Map loads, vehicles appear
- Click vehicle → detail panel + trail
- Switch to Coverage → vehicles hidden, coverage loads
- Slider, preset buttons, date picker work
- Switch lines/heatmap
- Switch back to Realtime → coverage cleared, vehicles visible
- Auto-refresh ticks

**Step 8: Commit**

```
refactor: add PlowApp class, move all state and coordination into it
```

---

### Task 6: Clean up — remove dead code and verify final state

**Files:**
- Modify: `src/where_the_plow/static/app.js`

**Step 1: Remove any orphaned standalone functions that were moved into classes**

Grep for any remaining direct `map.` references (should all be `plowMap.` or `this.map.` or `app.map.`). Remove any leftover `clearCoverageLayers`, `clearHeatmapLayer`, `clearTrail`, old `showTrail`, old `refreshTrail`, old `switchMode`, etc.

**Step 2: Verify section comments are updated**

Update the `/* ── ... ── */` section headers to reflect the new structure.

**Step 3: Run dev server and do a full manual test**

**Step 4: Commit**

```
refactor: clean up dead code after PlowMap/PlowApp extraction
```

---

### Task 7: Run tests

**Step 1: Run backend tests**

Run: `uv run pytest tests/ -v`
Expected: All 37 tests pass (no backend changes, but verify nothing broke).

**Step 2: Commit if any fixups needed**
