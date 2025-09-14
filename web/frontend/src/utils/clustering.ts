export interface ClusteringConfig {
    gapThreshold: number;
    clusterAcrossCategories: boolean;
    minimumConfidence: number;
}

export interface HarmfulContent {
    startTime: number;
    endTime: number;
    confidence: number; // 0-1 scale
    type: string;
}

export interface ClusteredHarmfulContent {
    id: string;
    startTime: number;
    endTime: number;
    duration: number;
    confidence: number; // Highest confidence in cluster for backward compatibility
    maxConfidence: number;
    avgConfidence: number;
    type: string; // Primary category
    eventCount: number;
    events: HarmfulContent[]; // Original individual events
    navigationTimestamp: number; // Timestamp of highest confidence event
    categories: string[]; // All categories in cluster
}

export function clusterHarmfulEvents(
    events: HarmfulContent[],
    config: ClusteringConfig = {
        gapThreshold: 2.5,
        clusterAcrossCategories: false,
        minimumConfidence: 0.1,
    },
): ClusteredHarmfulContent[] {
    // Step 1: Filter and sort events by timestamp
    const validEvents = events
        .filter((event) => event.confidence >= config.minimumConfidence)
        .sort((a, b) => a.startTime - b.startTime);

    if (validEvents.length === 0) return [];

    // Step 2: Pure time-based clustering (NO category grouping)
    const clusters: ClusteredHarmfulContent[] = [];
    let currentCluster: HarmfulContent[] = [validEvents[0]];
    let currentClusterEndTime = validEvents[0].endTime;

    for (let i = 1; i < validEvents.length; i++) {
        const currEvent = validEvents[i];

        // Calculate gap from END OF CURRENT CLUSTER to start of current event
        const gap = currEvent.startTime - currentClusterEndTime;

        if (gap <= config.gapThreshold) {
            // Add to current cluster and update cluster end time
            currentCluster.push(currEvent);
            currentClusterEndTime = Math.max(currentClusterEndTime, currEvent.endTime);
        } else {
            // Finalize current cluster and start new one
            clusters.push(createClusterFromEvents(currentCluster));
            currentCluster = [currEvent];
            currentClusterEndTime = currEvent.endTime;
        }
    }

    // Add final cluster
    if (currentCluster.length > 0) {
        clusters.push(createClusterFromEvents(currentCluster));
    }

    return clusters.sort((a, b) => a.startTime - b.startTime);
}

function createClusterFromEvents(events: HarmfulContent[]): ClusteredHarmfulContent {
    const highestConfidenceEvent = events.reduce((max, event) =>
        event.confidence > max.confidence ? event : max,
    );

    const startTime = Math.min(...events.map((e) => e.startTime));
    const endTime = Math.max(...events.map((e) => e.endTime));
    const avgConfidence =
        events.reduce((sum, e) => sum + e.confidence, 0) / events.length;

    // Get unique categories from all events in cluster
    const uniqueCategories = [...new Set(events.map((e) => e.type))];

    return {
        id: `cluster_${startTime.toFixed(2)}_${endTime.toFixed(2)}_${events.length}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        startTime,
        endTime,
        duration: endTime - startTime,
        confidence: highestConfidenceEvent.confidence,
        maxConfidence: Math.max(...events.map((e) => e.confidence)),
        avgConfidence,
        type: uniqueCategories.join(", "), // Combined categories for display
        eventCount: events.length,
        events: events,
        navigationTimestamp: highestConfidenceEvent.startTime,
        categories: uniqueCategories, // Array of all unique categories
    };
}

// Helper function to create single-event clusters for fallback
export function createSingleEventCluster(
    event: HarmfulContent,
): ClusteredHarmfulContent {
    return {
        id: `single_${event.startTime.toFixed(2)}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        startTime: event.startTime,
        endTime: event.endTime,
        duration: event.endTime - event.startTime,
        confidence: event.confidence,
        maxConfidence: event.confidence,
        avgConfidence: event.confidence,
        type: event.type,
        eventCount: 1,
        events: [event],
        navigationTimestamp: event.startTime,
        categories: [event.type],
    };
}
