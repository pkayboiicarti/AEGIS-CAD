function parseCoordinates(loc) {
    if (!loc) return null;
    if (typeof loc.lat === 'number' && typeof loc.lng === 'number' && !isNaN(loc.lat) && !isNaN(loc.lng)) {
        return { lat: loc.lat, lng: loc.lng };
    }
    if (typeof loc.latitude === 'number' && typeof loc.longitude === 'number' && !isNaN(loc.latitude) && !isNaN(loc.longitude)) {
        return { lat: loc.latitude, lng: loc.longitude };
    }
    if (Array.isArray(loc) && loc.length >= 2) {
        const lat = Number(loc[0]);
        const lng = Number(loc[1]);
        if (!isNaN(lat) && !isNaN(lng)) return { lat, lng };
    }
    if (typeof loc === 'string') {
        const match = loc.match(/(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)/);
        if (match) {
            const lat = parseFloat(match[1]);
            const lng = parseFloat(match[2]);
            if (!isNaN(lat) && !isNaN(lng)) return { lat, lng };
        }
    }
    return null;
}

function calcDistanceKm(lat1, lon1, lat2, lon2) {
    if (lat1 === undefined || lon1 === undefined || lat2 === undefined || lon2 === undefined) return 9999;
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

window.parseCoordinates = parseCoordinates;
window.calcDistanceKm = calcDistanceKm;


class CADMapManager {
    constructor(containerId = "tactical-map") {
        this.containerId = containerId;
        this.map = null;
        this.incidentMarkers = {};
        this.unitMarkers = {};
        this.stationMarkers = {};
        this.poiMarkers = [];
        this.routeLines = [];
        this.activeDispatchRoute = null;
        this.hazardCircles = [];
        this.activeFilterType = "ALL";
        this.activeFilterSeverity = "ALL";
        this.showStations = true;
        this.hasFittedBounds = false;
        this.nearestStationHighlight = null;
    }

    init() {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        if (this.map) {
            try {
                this.map.invalidateSize();
            } catch (e) {}
            return;
        }

        // Prevent Leaflet "Map container is already initialized" error
        if (container._leaflet_id) {
            try {
                container._leaflet_id = null;
            } catch (e) {}
        }

        try {
            // Initialize map centered at Chennai / Urban EOC
            this.map = L.map(this.containerId, {
                zoomControl: false,
                preferCanvas: true
            }).setView([13.0450, 80.2200], 12);

            // 1. OpenStreetMap Dark Tactical (100% Free & Open, Zero API Key Required)
            const osmDarkTiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                className: 'map-tiles-dark-theme',
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            });

            // 2. ESRI Dark Gray Canvas (100% Free Public GIS Layer, Zero API Key Required)
            const esriDarkTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 16,
                attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
            });

            // 3. OpenStreetMap Standard (100% Free, Zero API Key Required)
            const osmTiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            });

            // 4. ESRI Satellite Imagery (100% Free, Zero API Key Required)
            const satelliteTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 19,
                attribution: 'Tiles &copy; Esri'
            });

            // Set default active base layer to Open Dark Tactical
            osmDarkTiles.addTo(this.map);

            // Layer Switcher Control (Top Right)
            const baseMaps = {
                "🌑 Dark Tactical (OSM)": osmDarkTiles,
                "🌌 Dark Canvas (ESRI)": esriDarkTiles,
                "🗺️ OpenStreetMap": osmTiles,
                "🛰️ Satellite Imagery": satelliteTiles
            };
            L.control.layers(baseMaps, null, { position: 'topright' }).addTo(this.map);

            // Zoom controls bottom right
            L.control.zoom({ position: 'bottomright' }).addTo(this.map);

            // Handle initial dimension invalidations
            [50, 200, 500, 1000, 2000].forEach(delay => {
                setTimeout(() => {
                    if (this.map) {
                        try { this.map.invalidateSize(); } catch(e) {}
                    }
                }, delay);
            });

            window.addEventListener("resize", () => {
                if (this.map) {
                    try { this.map.invalidateSize(); } catch(e) {}
                }
            });
        } catch (err) {
            console.error("CAD Leaflet Map Initialization Error:", err);
        }
    }

    renderIncidents(incidents, onIncidentClick) {
        if (!this.map) this.init();
        if (!this.map) return;

        const currentIds = new Set(incidents.map(i => i.id));
        for (const [id, marker] of Object.entries(this.incidentMarkers)) {
            if (!currentIds.has(id)) {
                this.map.removeLayer(marker);
                delete this.incidentMarkers[id];
            }
        }

        this.hazardCircles.forEach(c => this.map.removeLayer(c));
        this.hazardCircles = [];

        const latLngList = [];

        incidents.forEach(inc => {
            if (this.activeFilterType !== "ALL" && inc.type !== this.activeFilterType) return;
            if (this.activeFilterSeverity !== "ALL" && inc.severity !== this.activeFilterSeverity) return;
            
            const coords = parseCoordinates(inc) || parseCoordinates({ lat: inc.latitude, lng: inc.longitude });
            if (!coords) return;
            const { lat, lng: lon } = coords;

            latLngList.push([lat, lon]);

            let color = "#ef4444"; // CRITICAL
            let bgGlow = "rgba(239, 68, 68, 0.4)";
            if (inc.severity === "HIGH") {
                color = "#f97316";
                bgGlow = "rgba(249, 115, 22, 0.4)";
            } else if (inc.severity === "MODERATE") {
                color = "#06b6d4";
                bgGlow = "rgba(6, 182, 212, 0.4)";
            } else if (inc.severity === "LOW") {
                color = "#10b981";
                bgGlow = "rgba(16, 185, 129, 0.4)";
            }

            const isCritical = (inc.urgency_score >= 80 || inc.severity === "CRITICAL");
            const markerHtml = `
                <div class="cad-pulse-marker ${isCritical ? 'critical-active' : ''}" style="--marker-color: ${color}; cursor: pointer;">
                    <div class="cad-pulse-ring" style="background: ${bgGlow}; border: 1px solid ${color};"></div>
                    <div class="marker-icon-inner" style="background: ${color}; border: 2px solid #fff;">
                        ${this._getTypeIcon(inc.type)}
                    </div>
                </div>
            `;

            const customIcon = L.divIcon({
                html: markerHtml,
                className: 'custom-cad-pin',
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            });

            if (this.incidentMarkers[inc.id]) {
                this.incidentMarkers[inc.id].setLatLng([lat, lon]);
                this.incidentMarkers[inc.id].setIcon(customIcon);
            } else {
                const marker = L.marker([lat, lon], { icon: customIcon }).addTo(this.map);
                
                marker.bindTooltip(`
                    <div style="background: #111827; color: #fff; padding: 6px 10px; border-radius: 6px; border: 1px solid ${color}; font-family: sans-serif; font-size: 11px;">
                        <strong style="color: ${color};">[${inc.severity}] ${inc.type}</strong><br/>
                        <span>${inc.title}</span><br/>
                        <span style="color: #9ca3af;">📍 ${inc.location_name || inc.locationName || 'Unknown Location'}</span><br/>
                        <span style="color: #fbbf24;">⚡ Urgency: ${inc.urgency_score !== undefined ? inc.urgency_score : inc.urgencyScore}/100</span>
                    </div>
                `, { direction: 'top', offset: [0, -10], opacity: 0.95 });

                marker.on('click', () => {
                    if (onIncidentClick) onIncidentClick(inc);
                });
                this.incidentMarkers[inc.id] = marker;
            }

            // Hazard circle
            if (inc.severity === "CRITICAL" || inc.severity === "HIGH") {
                const radiusMeters = inc.type === "INDUSTRIAL" ? 800 : (inc.type === "FLOOD" ? 1200 : 500);
                const circle = L.circle([lat, lon], {
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.12,
                    weight: 1,
                    dashArray: "4, 6",
                    radius: radiusMeters
                }).addTo(this.map);
                this.hazardCircles.push(circle);
            }
        });

        // Auto fit bounds on first load
        if (!this.hasFittedBounds && latLngList.length > 0) {
            try {
                this.map.fitBounds(latLngList, { padding: [50, 50], maxZoom: 13 });
                this.hasFittedBounds = true;
            } catch (e) {}
        }
    }

    renderUnits(units) {
        if (!this.map) return;

        this.routeLines.forEach(l => this.map.removeLayer(l));
        this.routeLines = [];

        units.forEach(u => {
            const coords = parseCoordinates(u);
            if (!coords) return;
            const { lat, lng: lon } = coords;

            const isDispatched = u.status === "DISPATCHED";
            const unitColor = isDispatched ? "#f59e0b" : "#3b82f6";
            
            const unitHtml = `
                <div style="background: #111827; border: 2px solid ${unitColor}; border-radius: 6px; padding: 3px 6px; display: flex; align-items: center; gap: 4px; box-shadow: 0 0 10px rgba(0,0,0,0.8); font-family: monospace; font-size: 10px; color: #fff; white-space: nowrap; cursor: pointer;">
                    <span style="width: 6px; height: 6px; border-radius: 50%; background: ${unitColor}; display: inline-block;"></span>
                    <span>${u.id}</span>
                </div>
            `;

            const icon = L.divIcon({
                html: unitHtml,
                className: 'custom-unit-pin',
                iconSize: [80, 24],
                iconAnchor: [40, 12]
            });

            if (this.unitMarkers[u.id]) {
                this.unitMarkers[u.id].setLatLng([lat, lon]);
                this.unitMarkers[u.id].setIcon(icon);
            } else {
                const marker = L.marker([lat, lon], { icon: icon }).addTo(this.map);
                marker.bindTooltip(`
                    <div style="background: #111827; color: #fff; padding: 4px 8px; border-radius: 4px; font-family: sans-serif; font-size: 11px;">
                        <strong>${u.name || u.call_sign || u.id}</strong> (${u.type || u.unit_type})<br/>
                        <span>Station: ${u.station_name || u.station_id || 'Command Center'}</span><br/>
                        <span>Status: <strong style="color: ${unitColor};">${u.status}</strong></span>
                    </div>
                `, { direction: 'top', offset: [0, -10] });
                this.unitMarkers[u.id] = marker;
            }

            // Route line to active incident
            if (isDispatched && u.assigned_incident_id && this.incidentMarkers[u.assigned_incident_id]) {
                const targetLatLng = this.incidentMarkers[u.assigned_incident_id].getLatLng();
                const route = L.polyline([[lat, lon], targetLatLng], {
                    color: "#f59e0b",
                    weight: 2,
                    dashArray: "6, 8",
                    opacity: 0.85
                }).addTo(this.map);
                this.routeLines.push(route);
            }
        });
    }

    renderStations(stations, incidents = [], selectedIncident = null, units = []) {
        if (!this.map || !stations) return;

        // Gather assigned station IDs from active dispatched units
        const assignedStationIds = new Set();
        if (units && units.length > 0) {
            units.forEach(u => {
                if (u.assigned_incident_id && (u.station_id || u.station_name)) {
                    if (u.station_id) assignedStationIds.add(u.station_id);
                }
            });
        }

        // Selected incident coordinates (if any)
        const selectedCoords = selectedIncident ? parseCoordinates(selectedIncident) : null;

        // Active incident coordinates
        const activeIncidentCoords = (incidents || [])
            .filter(inc => inc.status !== "RESOLVED" && inc.status !== "CLOSED")
            .map(inc => parseCoordinates(inc))
            .filter(Boolean);

        // FILTER: Only map stations when:
        // 1. A unit from that station is assigned/dispatched, OR
        // 2. Station is within 15 km of an active disaster in the queue, OR
        // 3. Station is within 25 km of the currently selected incident
        const relevantStations = stations.filter(s => {
            const coords = parseCoordinates(s);
            if (!coords) return false;

            // 1. Is an assigned response station?
            if (assignedStationIds.has(s.id)) return true;

            // 2. Is near selected incident?
            if (selectedCoords) {
                const distToSelected = calcDistanceKm(coords.lat, coords.lng, selectedCoords.lat, selectedCoords.lng);
                if (distToSelected <= 25.0) return true;
            }

            // 3. Is near any active disaster in Tamil Nadu queue?
            if (activeIncidentCoords.length > 0) {
                const isNearDisaster = activeIncidentCoords.some(incPt => {
                    return calcDistanceKm(coords.lat, coords.lng, incPt.lat, incPt.lng) <= 15.0;
                });
                if (isNearDisaster) return true;
            }

            return false;
        });

        // Remove unneeded distant station markers from map
        const relevantIds = new Set(relevantStations.map(s => s.id));
        for (const [id, marker] of Object.entries(this.stationMarkers)) {
            if (!relevantIds.has(id)) {
                this.map.removeLayer(marker);
                delete this.stationMarkers[id];
            }
        }

        // Render relevant stations with clean, non-flashing tactical styling
        relevantStations.forEach(s => {
            const coords = parseCoordinates(s);
            if (!coords) return;
            const { lat, lng: lon } = coords;

            let iconSymbol = "🏢";
            let borderColor = "#38bdf8";
            let bgColor = "rgba(15, 23, 42, 0.88)";
            let typeLabel = "STATION";

            if (s.type === "POLICE") {
                iconSymbol = "🚓";
                borderColor = "#3b82f6";
                bgColor = "rgba(15, 23, 42, 0.88)";
                typeLabel = "POLICE STATION";
            } else if (s.type === "FIRE") {
                iconSymbol = "🚒";
                borderColor = "#ef4444";
                bgColor = "rgba(15, 23, 42, 0.88)";
                typeLabel = "FIRE BASE";
            } else if (s.type === "HOSPITAL") {
                iconSymbol = "🏥";
                borderColor = "#10b981";
                bgColor = "rgba(15, 23, 42, 0.88)";
                typeLabel = "HOSPITAL / TRAUMA";
            } else if (s.type === "DISASTER_MGMT") {
                iconSymbol = "🏛️";
                borderColor = "#8b5cf6";
                bgColor = "rgba(15, 23, 42, 0.88)";
                typeLabel = "SDRF / NDRF HQ";
            }

            const stationHtml = `
                <div class="station-map-badge" style="background: ${bgColor}; border: 1px solid ${borderColor}; border-radius: 6px; padding: 2px 6px; display: flex; align-items: center; gap: 4px; cursor: pointer; color: #f8fafc; font-size: 10px; font-weight: 700; box-shadow: 0 2px 6px rgba(0,0,0,0.5);">
                    <span>${iconSymbol}</span>
                    <span style="font-size: 9.5px; font-family: monospace; color: #cbd5e1;">${s.id}</span>
                </div>
            `;

            const icon = L.divIcon({
                html: stationHtml,
                className: 'custom-station-pin',
                iconSize: [80, 22],
                iconAnchor: [40, 11]
            });

            if (this.stationMarkers[s.id]) {
                this.stationMarkers[s.id].setLatLng([lat, lon]);
                this.stationMarkers[s.id].setIcon(icon);
            } else {
                const marker = L.marker([lat, lon], { icon: icon }).addTo(this.map);
                marker.bindTooltip(`
                    <div style="background: #0f172a; color: #fff; padding: 6px 10px; border-radius: 6px; border: 1px solid ${borderColor}; font-family: sans-serif; font-size: 11px;">
                        <span style="color: ${borderColor}; font-weight: 700; text-transform: uppercase;">${iconSymbol} ${typeLabel}</span><br/>
                        <strong style="font-size: 12px;">${s.name}</strong><br/>
                        <span style="color: #94a3b8; font-size: 10px;">📍 ${s.address || 'Tamil Nadu Command Sector'}</span>
                    </div>
                `, { direction: 'top', offset: [0, -10] });
                this.stationMarkers[s.id] = marker;
            }
        });
    }

    renderPOIs(pois, onPoiClick) {
        if (!this.map) return;
        this.clearPOIs();

        pois.forEach(poi => {
            const coords = parseCoordinates(poi);
            if (!coords) return;
            const { lat, lng: lon } = coords;

            let symbol = "📍";
            let color = "#38bdf8";

            if (poi.type === "hospital") {
                symbol = "🏥";
                color = "#34d399";
            } else if (poi.type === "fire_station") {
                symbol = "🚒";
                color = "#f87171";
            } else if (poi.type === "police") {
                symbol = "🚓";
                color = "#60a5fa";
            }

            const html = `
                <div class="poi-pin-bubble" style="background: rgba(15, 23, 42, 0.92); border: 1px solid ${color}; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.5); cursor: pointer;">
                    ${symbol}
                </div>
            `;

            const icon = L.divIcon({
                html: html,
                className: 'custom-poi-pin',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            });

            const marker = L.marker([lat, lon], { icon: icon }).addTo(this.map);
            marker.bindTooltip(`
                <div style="background: #0f172a; color: #fff; padding: 4px 8px; border-radius: 4px; border: 1px solid ${color}; font-size: 11px;">
                    <strong>${symbol} ${poi.name}</strong><br/>
                    <span style="color: #94a3b8;">${poi.vicinity || ''}</span><br/>
                    <span style="color: #fbbf24; font-weight: 600;">Distance: ${poi.distance_km} km</span>
                </div>
            `, { direction: 'top', offset: [0, -8] });

            if (onPoiClick) {
                marker.on('click', () => onPoiClick(poi));
            }

            this.poiMarkers.push(marker);
        });
    }

    clearPOIs() {
        this.poiMarkers.forEach(m => this.map.removeLayer(m));
        this.poiMarkers = [];
    }

    highlightNearestStation(station, incidentCoord) {
        if (!this.map || !station) return;
        this.clearStationHighlight();

        const stnCoords = parseCoordinates(station);
        if (!stnCoords) return;

        // Steady, clean tactical perimeter circle (no flashing/pulsing)
        const steadyRing = L.circle([stnCoords.lat, stnCoords.lng], {
            radius: 100,
            color: "#38bdf8",
            weight: 1.5,
            dashArray: "4, 4",
            fillColor: "#0284c7",
            fillOpacity: 0.15,
            className: "steady-tactical-halo"
        }).addTo(this.map);

        const iconHtml = `
            <div style="background: rgba(15, 23, 42, 0.95); border: 1.5px solid #38bdf8; box-shadow: 0 4px 12px rgba(0,0,0,0.6); border-radius: 6px; padding: 3px 8px; color: #fff; font-size: 10.5px; font-weight: 700; white-space: nowrap; display: flex; align-items: center; gap: 5px;">
                <span style="background: #0284c7; color: #fff; padding: 1px 5px; border-radius: 3px; font-size: 9.5px; font-weight: 800;">⚡ NEAREST</span>
                <span>${station.name ? station.name.substring(0, 24) : 'Emergency Station'}</span>
            </div>
        `;

        const badgeMarker = L.marker([stnCoords.lat, stnCoords.lng], {
            icon: L.divIcon({
                html: iconHtml,
                className: "nearest-station-label-pin",
                iconSize: [180, 24],
                iconAnchor: [90, 30]
            })
        }).addTo(this.map);

        this.nearestStationHighlight = L.layerGroup([steadyRing, badgeMarker]).addTo(this.map);
    }

    clearStationHighlight() {
        if (this.nearestStationHighlight) {
            this.map.removeLayer(this.nearestStationHighlight);
            this.nearestStationHighlight = null;
        }
    }


    renderUnitRoute(routeData, originCoord, destCoord, unitInfo) {
        if (!this.map) return;
        this.clearUnitRoute();

        const startPt = parseCoordinates(originCoord);
        const endPt = parseCoordinates(destCoord);

        let latLngs = [];
        if (routeData && routeData.polyline) {
            latLngs = this._decodePolyline(routeData.polyline);
        } else if (routeData && routeData.coordinates && routeData.coordinates.length > 0) {
            latLngs = routeData.coordinates.map(pt => {
                const parsed = parseCoordinates(pt);
                return parsed ? [parsed.lat, parsed.lng] : pt;
            });
        } else if (startPt && endPt) {
            latLngs = [[startPt.lat, startPt.lng], [endPt.lat, endPt.lng]];
        }

        if (latLngs.length === 0) return;

        // Draw animated glowing vector polyline with neon cyan / amber dash
        const glowLine = L.polyline(latLngs, {
            color: "#0284c7",
            weight: 8,
            opacity: 0.45,
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(this.map);

        const routeLine = L.polyline(latLngs, {
            color: "#38bdf8",
            weight: 3.5,
            opacity: 0.98,
            dashArray: "6, 10",
            lineCap: 'round',
            className: 'tactical-dispatch-vector'
        }).addTo(this.map);

        this.activeDispatchRoute = L.layerGroup([glowLine, routeLine]).addTo(this.map);

        // Fit map bounds to show route with smooth transition
        try {
            this.map.fitBounds(latLngs, { padding: [60, 60], maxZoom: 15 });
        } catch (e) {}
    }

    clearUnitRoute() {
        if (this.activeDispatchRoute) {
            this.map.removeLayer(this.activeDispatchRoute);
            this.activeDispatchRoute = null;
        }
        this.clearStationHighlight();
    }



    _decodePolyline(encoded) {
        if (!encoded) return [];
        let points = [];
        let index = 0, len = encoded.length;
        let lat = 0, lng = 0;
        while (index < len) {
            let b, shift = 0, result = 0;
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);
            let dlat = ((result & 1) ? ~(result >> 1) : (result >> 1));
            lat += dlat;
            shift = 0;
            result = 0;
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);
            let dlng = ((result & 1) ? ~(result >> 1) : (result >> 1));
            lng += dlng;
            points.push([lat / 1e5, lng / 1e5]);
        }
        return points;
    }

    focusLocation(lat, lon, zoom = 14) {
        if (this.map) {
            this.map.flyTo([lat, lon], zoom, { duration: 1.0 });
        }
    }

    _getTypeIcon(type) {
        switch (type) {
            case "FIRE": return "🔥";
            case "FLOOD": return "🌊";
            case "INDUSTRIAL": return "☣️";
            case "EARTHQUAKE": return "🌋";
            case "CYCLONE": return "🌀";
            case "STRUCTURAL_COLLAPSE": return "🏚️";
            default: return "⚠️";
        }
    }
}

window.cadMapManager = new CADMapManager();
