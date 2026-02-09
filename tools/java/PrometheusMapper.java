import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.*;
import java.util.stream.Collectors;

/**
 * Prometheus to Dimensional Model Mapper
 * 
 * Transformiert Prometheus-Metriken in ein fixes dimensionales Schema:
 * ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric
 * 
 * Regeln:
 * 1. ProcessGroup = job (1:1)
 * 2. Process = instance URL (vollständig)
 * 3. Host = erster Teil von instance (vor dem Punkt)
 * 4. HostGroup = "cluster" (konstant)
 * 5. MetricGroup = job + rekursive Erweiterung bei vielen Varianten
 * 6. Metric = Metrikname (ohne job-Präfix) + Labels als suffix
 * 
 * Verwendung:
 * <pre>
 * // Einfach: Alles von Prometheus laden und analysieren
 * PrometheusMapper mapper = new PrometheusMapper(100);
 * mapper.loadFromPrometheus("http://node0.cloud.local:9090");
 * 
 * // Dann transformieren
 * DimensionalMetric result = mapper.transform(metric);
 * 
 * // Oder alle auf einmal
 * List&lt;DimensionalMetric&gt; all = mapper.transformAllLoaded();
 * </pre>
 */
public class PrometheusMapper {

    // ========================================================================
    // Konfiguration
    // ========================================================================

    /** Labels die ignoriert werden (redundant oder konstant) */
    private static final Set<String> IGNORE_LABELS = Set.of(
        "base_url", "cluster_id", "core", "fstype", "__name__"
    );

    /** Standard-Labels (werden zu ProcessGroup/Process/Host) */
    private static final Set<String> STANDARD_LABELS = Set.of("job", "instance");

    /** Quantil → Suffix Mapping */
    private static final Map<String, String> QUANTILE_SUFFIX = Map.of(
        "0.5", "_p50",
        "0.75", "_p75",
        "0.9", "_p90",
        "0.95", "_p95",
        "0.99", "_p99",
        "0.999", "_p999",
        "1", "_p100"
    );

    /** Schwellwert für MetricGroup-Erweiterung */
    private final int threshold;

    /** Präfix-Zählungen für rekursive Erweiterung: (job, prefix) → count */
    private final Map<PrefixKey, Integer> prefixCounts = new HashMap<>();

    /** Geladene Metriken von Prometheus */
    private final List<PrometheusMetric> loadedMetrics = new ArrayList<>();

    /** HTTP Client für Prometheus API */
    private final HttpClient httpClient = HttpClient.newBuilder()
        .connectTimeout(java.time.Duration.ofSeconds(30))
        .build();

    // ========================================================================
    // Datenstrukturen
    // ========================================================================

    /**
     * Eingabe: Eine Prometheus-Metrik mit Labels.
     */
    public record PrometheusMetric(
        String name,
        Map<String, String> labels
    ) {
        public String getLabel(String key) {
            return labels.getOrDefault(key, "");
        }
        
        public String job() {
            return getLabel("job");
        }
        
        public String instance() {
            return getLabel("instance");
        }
    }

    /**
     * Ausgabe: Eine transformierte dimensionale Metrik.
     */
    public record DimensionalMetric(
        String processGroup,
        String process,
        String hostGroup,
        String host,
        String metricGroup,
        String metric
    ) {}

    /**
     * Schlüssel für Präfix-Zählungen.
     */
    private record PrefixKey(String job, String prefix) {}

    // ========================================================================
    // Konstruktor
    // ========================================================================

    /**
     * Erstellt einen neuen Mapper mit dem angegebenen Threshold.
     * 
     * @param threshold Schwellwert für MetricGroup-Erweiterung (empfohlen: 100)
     */
    public PrometheusMapper(int threshold) {
        this.threshold = threshold;
    }

    /**
     * Erstellt einen neuen Mapper mit Default-Threshold (100).
     */
    public PrometheusMapper() {
        this(100);
    }

    // ========================================================================
    // Prometheus Client - Laden und Analysieren
    // ========================================================================

    /**
     * Lädt alle Metriken von Prometheus und führt die Analyse durch.
     * 
     * Diese Methode muss aufgerufen werden bevor transform() korrekt funktioniert!
     * 
     * @param prometheusUrl Prometheus URL (z.B. "http://node0.cloud.local:9090")
     * @throws IOException bei Verbindungsproblemen
     */
    public void loadFromPrometheus(String prometheusUrl) throws IOException, InterruptedException {
        String baseUrl = prometheusUrl.replaceAll("/+$", "");
        
        System.out.println("Lade Metriken von " + baseUrl + "...");
        
        // 1. Alle Metriknamen holen
        List<String> metricNames = getMetricNames(baseUrl);
        System.out.println("  " + metricNames.size() + " Metriknamen gefunden");
        
        // 2. Alle Serien (Label-Kombinationen) holen
        loadedMetrics.clear();
        int batchSize = 50;
        
        for (int i = 0; i < metricNames.size(); i += batchSize) {
            List<String> batch = metricNames.subList(i, Math.min(i + batchSize, metricNames.size()));
            List<PrometheusMetric> series = getSeriesForMetrics(baseUrl, batch);
            loadedMetrics.addAll(series);
            
            if ((i + batchSize) % 200 == 0) {
                System.out.println("  Serien abgerufen: " + Math.min(i + batchSize, metricNames.size()) + "/" + metricNames.size());
            }
        }
        System.out.println("  " + loadedMetrics.size() + " Serien geladen");
        
        // 3. Analyse durchführen
        prefixCounts.clear();
        analyzeAll(loadedMetrics);
        System.out.println("  " + prefixCounts.size() + " Präfixe analysiert");
        
        // 4. Statistik ausgeben
        long highVariantCount = prefixCounts.values().stream().filter(c -> c > threshold).count();
        System.out.println("  " + highVariantCount + " Präfixe über Threshold (" + threshold + ")");
    }

    /**
     * Holt alle Metriknamen von Prometheus.
     */
    private List<String> getMetricNames(String baseUrl) throws IOException, InterruptedException {
        String url = baseUrl + "/api/v1/label/__name__/values";
        String json = httpGet(url);
        
        // Einfaches JSON-Parsing für ["metric1", "metric2", ...]
        List<String> names = new ArrayList<>();
        Matcher matcher = Pattern.compile("\"([^\"]+)\"").matcher(
            json.substring(json.indexOf("["), json.lastIndexOf("]") + 1)
        );
        while (matcher.find()) {
            names.add(matcher.group(1));
        }
        return names;
    }

    /**
     * Holt alle Serien für eine Batch von Metriken.
     */
    private List<PrometheusMetric> getSeriesForMetrics(String baseUrl, List<String> metricNames) 
            throws IOException, InterruptedException {
        
        StringBuilder url = new StringBuilder(baseUrl + "/api/v1/series?");
        for (String name : metricNames) {
            url.append("match[]=").append(URLEncoder.encode(name, StandardCharsets.UTF_8)).append("&");
        }
        
        String json = httpGet(url.toString());
        return parseSeriesJson(json);
    }

    /**
     * Parst die Series-JSON-Antwort von Prometheus.
     */
    private List<PrometheusMetric> parseSeriesJson(String json) {
        List<PrometheusMetric> metrics = new ArrayList<>();
        
        // Finde "data": [...]
        int dataStart = json.indexOf("\"data\"");
        if (dataStart == -1) return metrics;
        
        int arrayStart = json.indexOf("[", dataStart);
        int arrayEnd = findMatchingBracket(json, arrayStart);
        if (arrayStart == -1 || arrayEnd == -1) return metrics;
        
        String dataArray = json.substring(arrayStart + 1, arrayEnd);
        
        // Parse jedes Objekt {...}
        int depth = 0;
        int objStart = -1;
        
        for (int i = 0; i < dataArray.length(); i++) {
            char c = dataArray.charAt(i);
            if (c == '{') {
                if (depth == 0) objStart = i;
                depth++;
            } else if (c == '}') {
                depth--;
                if (depth == 0 && objStart >= 0) {
                    String obj = dataArray.substring(objStart, i + 1);
                    PrometheusMetric metric = parseMetricObject(obj);
                    if (metric != null) {
                        metrics.add(metric);
                    }
                    objStart = -1;
                }
            }
        }
        
        return metrics;
    }

    /**
     * Parst ein einzelnes Metrik-Objekt.
     */
    private PrometheusMetric parseMetricObject(String obj) {
        Map<String, String> labels = new HashMap<>();
        
        // Parse "key":"value" Paare
        Matcher matcher = Pattern.compile("\"([^\"]+)\"\\s*:\\s*\"([^\"]*)\"").matcher(obj);
        while (matcher.find()) {
            labels.put(matcher.group(1), matcher.group(2));
        }
        
        String name = labels.remove("__name__");
        if (name == null) {
            // Für series ohne __name__ den ersten Match nehmen
            return null;
        }
        
        return new PrometheusMetric(name, labels);
    }

    /**
     * Findet die schließende Klammer.
     */
    private int findMatchingBracket(String s, int start) {
        if (start < 0 || start >= s.length()) return -1;
        char open = s.charAt(start);
        char close = open == '[' ? ']' : open == '{' ? '}' : 0;
        if (close == 0) return -1;
        
        int depth = 1;
        for (int i = start + 1; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == open) depth++;
            else if (c == close) {
                depth--;
                if (depth == 0) return i;
            }
        }
        return -1;
    }

    /**
     * HTTP GET Anfrage.
     */
    private String httpGet(String url) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .timeout(java.time.Duration.ofSeconds(60))
            .GET()
            .build();
        
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        
        if (response.statusCode() != 200) {
            throw new IOException("HTTP " + response.statusCode() + ": " + response.body());
        }
        
        return response.body();
    }

    /**
     * Transformiert alle geladenen Metriken.
     * 
     * @return Liste aller transformierten Metriken (dedupliziert)
     */
    public List<DimensionalMetric> transformAllLoaded() {
        Set<DimensionalMetric> seen = new LinkedHashSet<>();
        for (PrometheusMetric metric : loadedMetrics) {
            DimensionalMetric dm = transform(metric);
            if (dm != null) {
                seen.add(dm);
            }
        }
        return new ArrayList<>(seen);
    }

    /**
     * Gibt die Anzahl geladener Metriken zurück.
     */
    public int getLoadedMetricCount() {
        return loadedMetrics.size();
    }

    // ========================================================================
    // Analyse-Phase
    // ========================================================================

    /**
     * Analysiert eine Metrik und aktualisiert die Präfix-Statistiken.
     * 
     * MUSS für alle Metriken aufgerufen werden BEVOR transform() verwendet wird.
     */
    public void analyze(PrometheusMetric metric) {
        if (isInfoMetric(metric.name())) {
            return;
        }

        String job = metric.job();
        String stripped = stripJobPrefix(metric.name(), job);

        // Zähle für alle Präfix-Längen
        String[] parts = stripped.split("_");
        StringBuilder prefix = new StringBuilder();
        
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) {
                prefix.append("_");
            }
            prefix.append(parts[i]);
            
            PrefixKey key = new PrefixKey(job, prefix.toString());
            prefixCounts.merge(key, 1, Integer::sum);
        }
    }

    /**
     * Analysiert mehrere Metriken.
     */
    public void analyzeAll(Collection<PrometheusMetric> metrics) {
        for (PrometheusMetric metric : metrics) {
            analyze(metric);
        }
    }

    // ========================================================================
    // Transformation
    // ========================================================================

    /**
     * Transformiert eine Prometheus-Metrik in das dimensionale Schema.
     * 
     * @param metric Die zu transformierende Metrik
     * @return Die transformierte dimensionale Metrik, oder null wenn ignoriert
     */
    public DimensionalMetric transform(PrometheusMetric metric) {
        // Info-Metriken ignorieren
        if (isInfoMetric(metric.name())) {
            return null;
        }

        String job = metric.job();
        String instance = metric.instance();

        // Job-Präfix entfernen
        String stripped = stripJobPrefix(metric.name(), job);

        // MetricGroup bestimmen (rekursiv basierend auf Präfix-Zählungen)
        String[] expansion = determineExpansion(stripped, job);
        String groupExtension = expansion[0];
        String baseMetric = expansion[1];

        // MetricGroup bauen
        String metricGroup;
        if (!groupExtension.isEmpty()) {
            metricGroup = job.isEmpty() ? groupExtension : job + "_" + groupExtension;
        } else {
            metricGroup = job.isEmpty() ? stripped.split("_")[0] : job;
        }

        // Label-Suffix bauen
        String[] suffixes = buildLabelSuffix(metric.labels());
        String labelSuffix = suffixes[0];
        String quantileSuffix = suffixes[1];

        // Metric zusammenbauen
        String finalMetric = baseMetric;
        if (!labelSuffix.isEmpty()) {
            finalMetric = finalMetric + "_" + labelSuffix;
        }
        if (quantileSuffix != null) {
            finalMetric = finalMetric + quantileSuffix;
        }

        return new DimensionalMetric(
            job,
            instance,
            "cluster",
            extractHost(instance),
            metricGroup,
            finalMetric
        );
    }

    /**
     * Transformiert mehrere Metriken.
     */
    public List<DimensionalMetric> transformAll(Collection<PrometheusMetric> metrics) {
        return metrics.stream()
            .map(this::transform)
            .filter(Objects::nonNull)
            .collect(Collectors.toList());
    }

    // ========================================================================
    // Hilfsmethoden
    // ========================================================================

    /**
     * Prüft ob es eine _info Metrik ist (werden ignoriert).
     */
    private boolean isInfoMetric(String metricName) {
        return metricName.endsWith("_info");
    }

    /**
     * Entfernt das Job-Präfix vom Metriknamen wenn vorhanden.
     */
    private String stripJobPrefix(String metricName, String job) {
        if (!job.isEmpty() && metricName.startsWith(job + "_")) {
            return metricName.substring(job.length() + 1);
        }
        return metricName;
    }

    /**
     * Extrahiert den Host aus der instance URL.
     */
    private String extractHost(String instance) {
        if (instance == null || instance.isEmpty()) {
            return "";
        }
        // node1.cloud.local:9100 → node1
        int dotIndex = instance.indexOf('.');
        if (dotIndex > 0) {
            return instance.substring(0, dotIndex);
        }
        // Falls kein Punkt: vor dem Doppelpunkt
        int colonIndex = instance.indexOf(':');
        if (colonIndex > 0) {
            return instance.substring(0, colonIndex);
        }
        return instance;
    }

    /**
     * Bestimmt rekursiv wie viel vom Metriknamen in die MetricGroup verschoben wird.
     * 
     * @return Array mit [groupExtension, remainingMetric]
     */
    private String[] determineExpansion(String strippedMetric, String job) {
        String[] parts = strippedMetric.split("_");

        if (parts.length <= 1) {
            return new String[]{"", strippedMetric};
        }

        // Rekursiv den optimalen Split-Punkt finden
        int bestSplit = 0;
        StringBuilder prefix = new StringBuilder();

        for (int i = 0; i < parts.length - 1; i++) {
            if (i > 0) {
                prefix.append("_");
            }
            prefix.append(parts[i]);

            PrefixKey key = new PrefixKey(job, prefix.toString());
            int count = prefixCounts.getOrDefault(key, 0);

            if (count > threshold) {
                // Dieser Präfix hat noch zu viele → erweitern
                bestSplit = i + 1;
            } else {
                // Unter threshold → hier aufhören
                break;
            }
        }

        if (bestSplit == 0) {
            return new String[]{"", strippedMetric};
        }

        String groupExt = String.join("_", Arrays.copyOfRange(parts, 0, bestSplit));
        String remaining = String.join("_", Arrays.copyOfRange(parts, bestSplit, parts.length));

        return new String[]{groupExt, remaining};
    }

    /**
     * Baut den Label-Suffix für den Metriknamen.
     * 
     * @return Array mit [suffix, quantileSuffix]
     */
    private String[] buildLabelSuffix(Map<String, String> labels) {
        Map<String, String> filteredLabels = new TreeMap<>(); // alphabetisch sortiert
        String quantileSuffix = null;

        for (Map.Entry<String, String> entry : labels.entrySet()) {
            String label = entry.getKey();
            String value = entry.getValue();

            // Standard und ignorierte Labels überspringen
            if (STANDARD_LABELS.contains(label) || IGNORE_LABELS.contains(label)) {
                continue;
            }

            // Histogram-Spezialbehandlung
            if ("quantile".equals(label)) {
                quantileSuffix = QUANTILE_SUFFIX.getOrDefault(value, 
                    "_p" + value.replace(".", ""));
                continue;
            }
            if ("le".equals(label)) {
                // le-Labels werden ignoriert (nur _sum/_count verwenden)
                continue;
            }

            filteredLabels.put(label, value);
        }

        // Suffix bauen: alphabetisch sortiert
        StringBuilder suffix = new StringBuilder();
        for (Map.Entry<String, String> entry : filteredLabels.entrySet()) {
            if (suffix.length() > 0) {
                suffix.append("_");
            }
            // Sonderzeichen im Value behandeln
            String safeValue = entry.getValue()
                .replace("/", "_")
                .replace(" ", "_");
            suffix.append(entry.getKey()).append("_").append(safeValue);
        }

        return new String[]{suffix.toString(), quantileSuffix};
    }

    // ========================================================================
    // Statistik
    // ========================================================================

    /**
     * Gibt die Anzahl der analysierten Präfixe zurück.
     */
    public int getPrefixCount() {
        return prefixCounts.size();
    }

    /**
     * Gibt den Threshold zurück.
     */
    public int getThreshold() {
        return threshold;
    }

    // ========================================================================
    // Main (für Tests)
    // ========================================================================

    public static void main(String[] args) {
        PrometheusMapper mapper = new PrometheusMapper(100);

        // Option 1: Von Prometheus laden (wenn URL als Argument übergeben)
        if (args.length > 0) {
            String prometheusUrl = args[0];
            try {
                mapper.loadFromPrometheus(prometheusUrl);
                
                List<DimensionalMetric> results = mapper.transformAllLoaded();
                System.out.println("\n" + results.size() + " dimensionale Metriken:\n");
                System.out.println("ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric");
                System.out.println("-".repeat(100));
                
                // Nur erste 100 zeigen
                results.stream()
                    .limit(100)
                    .forEach(dm -> System.out.printf("%s | %s | %s | %s | %s | %s%n",
                        dm.processGroup(),
                        dm.process(),
                        dm.hostGroup(),
                        dm.host(),
                        dm.metricGroup(),
                        dm.metric()
                    ));
                
                if (results.size() > 100) {
                    System.out.println("... und " + (results.size() - 100) + " weitere");
                }
                
                // Statistik
                System.out.println("\n=== Statistik ===");
                Map<String, Long> groups = results.stream()
                    .collect(Collectors.groupingBy(DimensionalMetric::metricGroup, Collectors.counting()));
                
                System.out.println("MetricGroups: " + groups.size());
                groups.entrySet().stream()
                    .sorted(Map.Entry.<String, Long>comparingByValue().reversed())
                    .limit(20)
                    .forEach(e -> System.out.printf("  %s: %d%n", e.getKey(), e.getValue()));
                
            } catch (Exception e) {
                System.err.println("Fehler: " + e.getMessage());
                e.printStackTrace();
            }
            return;
        }

        // Option 2: Beispiel-Metriken (wenn keine URL übergeben)
        System.out.println("Verwendung: java PrometheusMapper.java <prometheus-url>");
        System.out.println("Beispiel:   java PrometheusMapper.java http://node0.cloud.local:9090");
        System.out.println("\nDemo mit Beispiel-Metriken:\n");
        
        List<PrometheusMetric> metrics = List.of(
            new PrometheusMetric("solr_metrics_core_errors_total", Map.of(
                "job", "solr",
                "instance", "node1.cloud.local:9854",
                "category", "QUERY",
                "collection", "nyc_taxi",
                "shard", "shard1"
            )),
            new PrometheusMetric("node_cpu_seconds_total", Map.of(
                "job", "node",
                "instance", "node1.cloud.local:9100",
                "cpu", "0",
                "mode", "idle"
            )),
            new PrometheusMetric("avg_latency", Map.of(
                "job", "zookeeper",
                "instance", "node1.cloud.local:7070"
            )),
            new PrometheusMetric("jvm_memory_bytes_used", Map.of(
                "job", "spark",
                "instance", "node0.cloud.local:9404",
                "area", "heap"
            ))
        );

        mapper.analyzeAll(metrics);
        System.out.println("Analysierte Präfixe: " + mapper.getPrefixCount());

        System.out.println("\nTransformierte Metriken:");
        System.out.println("ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric");
        System.out.println("-".repeat(100));
        
        for (DimensionalMetric dm : mapper.transformAll(metrics)) {
            System.out.printf("%s | %s | %s | %s | %s | %s%n",
                dm.processGroup(),
                dm.process(),
                dm.hostGroup(),
                dm.host(),
                dm.metricGroup(),
                dm.metric()
            );
        }
    }
}
