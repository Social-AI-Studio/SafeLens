"use client";

import { useState } from "react";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

interface ModelSelectorProps {
    value?: string;
    onModelChange?: (model: string) => void;
}

const models = [
    { value: "SafeLens/llama-3-8b", label: "Llama 3 8B (FT)" },
    { value: "meta-llama/llama-3-8b-instruct", label: "Llama 3 8B" },
    { value: "meta-llama/llama-3.1-8b-instruct", label: "Llama 3.1 8B" },
    { value: "google/gemini-3-flash-preview", label: "Gemini 3 Flash (Preview)" },
    { value: "openai/gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "anthropic/claude-3.5-haiku", label: "Claude 3.5 Haiku" },
    { value: "mistralai/mistral-7b-instruct", label: "Mistral 7B Instruct" },
    { value: "qwen/qwen-2.5-7b-instruct", label: "Qwen 2.5 7B Instruct" },
];

export default function ModelSelector({ value, onModelChange }: ModelSelectorProps) {
    const handleModelChange = (model: string) => {
        onModelChange?.(model);
    };

    return (
        <div className="flex items-center gap-3">
            <Label
                htmlFor="model-selector"
                className="text-sm font-medium whitespace-nowrap"
            >
                Analysis Model:
            </Label>
            <Select
                value={value || "SafeLens/llama-3-8b"}
                onValueChange={handleModelChange}
            >
                <SelectTrigger id="model-selector" className="w-[200px]">
                    <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                    {models.map((model) => (
                        <SelectItem key={model.value} value={model.value}>
                            {model.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}
