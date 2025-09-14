import { ClusteringConfig, ClusteredHarmfulContent } from "@/utils/clustering";

export interface HarmfulContent {
    startTime: number;
    endTime: number;
    confidence: number;
    type: string;
    description?: string;
    evidence?: string;
    source?: "vision" | "audio" | "ocr" | "multimodal";
    detectionMethod?: string;
    categories?: string[];
    rawData?: any; // Store original backend event data
}

export interface TranscriptionWord {
    word: string;
    start: number;
}

export interface TranscriptionLine {
    start: number;
    end: number;
    words: TranscriptionWord[];
    text: string;
}

export interface AnalysisData {
    summary: string;
    transcription: string;
    harmfulContent: HarmfulContent[]; // Keep original for backward compatibility
    clusteredHarmfulContent?: ClusteredHarmfulContent[]; // New clustered data
    analysisModel?: string;
    clusteringConfig?: ClusteringConfig;
    transcriptionWords?: TranscriptionWord[]; // Word-level timestamps for synced lyrics
    transcriptionLines?: TranscriptionLine[]; // Optional cached line segmentation
}

export interface HarmfulContentMarker {
    time: number; // Maps to navigationTimestamp for VideoPlayer compatibility
    endTime: number;
    confidence: number;
    eventCount?: number;
    categories?: string[];
}

// Re-export clustering types for convenience
export type { ClusteringConfig, ClusteredHarmfulContent } from "@/utils/clustering";
