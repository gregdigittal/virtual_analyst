"use client";

import { useCallback } from "react";
import { VAInput, VABadge } from "@/components/ui";

export interface DetectedEntity {
  entity_name: string;
  industry: string;
  is_parent: boolean;
  children: string[];
}

interface EntityHierarchyEditorProps {
  entities: DetectedEntity[];
  onChange: (entities: DetectedEntity[]) => void;
}

export function EntityHierarchyEditor({ entities, onChange }: EntityHierarchyEditorProps) {
  const parentEntities = entities.filter((e) => e.is_parent);
  const childNames = new Set(parentEntities.flatMap((p) => p.children));
  const orphans = entities.filter((e) => !e.is_parent && !childNames.has(e.entity_name));

  const updateEntity = useCallback(
    (index: number, field: keyof DetectedEntity, value: string) => {
      const updated = entities.map((e, i) => {
        if (i !== index) return e;
        return { ...e, [field]: value };
      });
      onChange(updated);
    },
    [entities, onChange],
  );

  const findEntityIndex = useCallback(
    (name: string) => entities.findIndex((e) => e.entity_name === name),
    [entities],
  );

  return (
    <div className="space-y-4">
      {parentEntities.map((parent) => {
        const parentIdx = findEntityIndex(parent.entity_name);
        return (
          <div key={parent.entity_name} className="rounded-va-sm border border-va-border p-3">
            <div className="flex items-center gap-2 mb-2">
              <VABadge variant="success">Parent</VABadge>
              <VAInput
                value={parent.entity_name}
                onChange={(e) => updateEntity(parentIdx, "entity_name", e.target.value)}
                className="flex-1"
                aria-label={`Entity name for ${parent.entity_name}`}
              />
              <VAInput
                value={parent.industry}
                onChange={(e) => updateEntity(parentIdx, "industry", e.target.value)}
                className="w-48"
                aria-label={`Industry for ${parent.entity_name}`}
              />
            </div>
            {parent.children.length > 0 && (
              <div className="ml-6 space-y-2">
                {parent.children.map((childName) => {
                  const childIdx = findEntityIndex(childName);
                  const child = childIdx >= 0 ? entities[childIdx] : null;
                  if (!child) return null;
                  return (
                    <div key={childName} className="flex items-center gap-2">
                      <span className="text-va-text2 text-xs">└</span>
                      <VAInput
                        value={child.entity_name}
                        onChange={(e) => updateEntity(childIdx, "entity_name", e.target.value)}
                        className="flex-1"
                        aria-label={`Entity name for ${childName}`}
                      />
                      <VAInput
                        value={child.industry}
                        onChange={(e) => updateEntity(childIdx, "industry", e.target.value)}
                        className="w-48"
                        aria-label={`Industry for ${childName}`}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      {orphans.map((entity) => {
        const idx = findEntityIndex(entity.entity_name);
        return (
          <div key={entity.entity_name} className="rounded-va-sm border border-va-border p-3">
            <div className="flex items-center gap-2">
              <VABadge variant="warning">Unlinked</VABadge>
              <VAInput
                value={entity.entity_name}
                onChange={(e) => updateEntity(idx, "entity_name", e.target.value)}
                className="flex-1"
                aria-label={`Entity name for ${entity.entity_name}`}
              />
              <VAInput
                value={entity.industry}
                onChange={(e) => updateEntity(idx, "industry", e.target.value)}
                className="w-48"
                aria-label={`Industry for ${entity.entity_name}`}
              />
            </div>
          </div>
        );
      })}

      {entities.length === 0 && (
        <p className="text-sm text-va-text2">No entities detected.</p>
      )}
    </div>
  );
}
