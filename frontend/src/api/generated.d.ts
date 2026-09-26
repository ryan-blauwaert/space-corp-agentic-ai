// Generated from FastAPI OpenAPI. Run pnpm types:generate; do not edit.
export interface paths {
    "/components": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Components
         * @description Browse shared revisions ordered by code then ID, optionally within a release.
         *
         *     Unknown release IDs return an empty page. Workspace selection does not restrict
         *     these shared definitions; totals reflect the release filter before pagination.
         */
        get: operations["listComponents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/components/{component_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Component */
        get: operations["getComponent"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/equipment-models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Equipment Models
         * @description Browse shared revisions ordered by code then ID, optionally within a release.
         *
         *     Unknown release IDs return an empty page. Workspace selection does not restrict
         *     these shared definitions; totals reflect the release filter before pagination.
         */
        get: operations["listEquipmentModels"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/equipment-models/{equipment_model_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Equipment Model */
        get: operations["getEquipmentModel"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/equipment-models/{equipment_model_id}/components": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Compatible Components
         * @description Compatibility with this exact model revision; does not imply fault repair.
         */
        get: operations["listCompatibleComponents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/equipment-units": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Equipment Units
         * @description Workspace units ordered by asset tag then ID. Optional filters combine with AND.
         */
        get: operations["listEquipmentUnits"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/equipment-units/{equipment_unit_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Equipment Unit */
        get: operations["getEquipmentUnit"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/facilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Facilities
         * @description List scoped facilities with stored body/system context and local location.
         */
        get: operations["listFacilities"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/facilities/{facility_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Facility
         * @description Read a scoped facility; body_or_system is null when not recorded.
         */
        get: operations["getFacility"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["getHealth"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/incidents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Incidents
         * @description Workspace incidents ordered by occurrence time then ID. Optional filters combine with AND; time bounds are inclusive from, exclusive before.
         */
        get: operations["listIncidents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/incidents/{incident_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Incident */
        get: operations["getIncident"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/inventory-items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Inventory Items
         * @description Recorded workspace stock ordered by ID. Missing stock rows are not zero quantities. Optional filters combine with AND.
         */
        get: operations["listInventoryItems"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/inventory-items/{inventory_item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Inventory Item */
        get: operations["getInventoryItem"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/questions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Ask Question
         * @description Plan one bounded question; unanchored scope returns for review without execution.
         *
         *     Executed evidence includes stored display names/codes where available. Answer prose
         *     prefers those labels; exact UUIDs remain in evidence and record references.
         */
        post: operations["askQuestion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/questions/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirm Question Scope
         * @description Approve the exact displayed plan. Consume its handle once, without replanning.
         */
        post: operations["confirmQuestionScope"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/work-orders": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Work Orders
         * @description Workspace work orders ordered by reference code then ID. Optional filters combine with AND. Due times are returned without an implicit current-time overdue calculation.
         */
        get: operations["listWorkOrders"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/work-orders/{work_order_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Work Order */
        get: operations["getWorkOrder"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * Answered
         * @description Application output after validation; never accept directly from the model.
         */
        Answered: {
            answer: components["schemas"]["RenderedAnswer"];
            /**
             * Coverage
             * @enum {string}
             */
            coverage: "complete" | "partial";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            status: "answered";
        };
        /** CautiousAnswer */
        CautiousAnswer: {
            /**
             * Reason
             * @enum {string}
             */
            reason: "no_results" | "insufficient_evidence" | "awaiting_confirmation" | "declined" | "invalid_answer" | "model_failure";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            status: "cautious";
            /** Text */
            text: string;
        };
        /** CompatibleStockEvidence */
        CompatibleStockEvidence: {
            /** Component Code */
            component_code?: string | null;
            /**
             * Component Id
             * Format: uuid
             */
            component_id: string;
            /** Component Name */
            component_name?: string | null;
            /** Inventory Id */
            inventory_id: string | null;
            /** Model Code */
            model_code?: string | null;
            /**
             * Model Id
             * Format: uuid
             */
            model_id: string;
            /** Model Name */
            model_name?: string | null;
            /** Quantity On Hand */
            quantity_on_hand: number | null;
        };
        /** CompatibleStockPlan */
        CompatibleStockPlan: {
            /**
             * Equipment Unit Id
             * Format: uuid
             */
            equipment_unit_id: string;
            /** Incident Statuses */
            incident_statuses?: components["schemas"]["IncidentStatus"][] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "compatible_stock";
        };
        /** CompatibleStockResult */
        CompatibleStockResult: {
            /**
             * Incident Codes
             * @default []
             */
            incident_codes: string[];
            /** Incident Ids */
            incident_ids: string[];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "compatible_stock";
            page: components["schemas"]["EvidencePage_CompatibleStockEvidence_"];
            /**
             * Status
             * @enum {string}
             */
            status: "matched" | "no_incident_match" | "no_compatibility";
        };
        /** ComponentListResponse */
        ComponentListResponse: {
            /** Items */
            items: components["schemas"]["ComponentResponse"][];
            pagination: components["schemas"]["PaginationMetadata"];
        };
        /** ComponentResponse */
        ComponentResponse: {
            /**
             * Catalog Release Id
             * Format: uuid
             */
            catalog_release_id: string;
            /** Code */
            code: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /** ConfirmationRequest */
        ConfirmationRequest: {
            /** Confirmation Id */
            confirmation_id: string;
        };
        /**
         * DeclinedPlan
         * @description Terminal planning outcome; does not authorize partial query execution.
         */
        DeclinedPlan: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "declined";
            /**
             * Reason
             * @enum {string}
             */
            reason: "unsupported_question" | "prohibited_operation" | "missing_input" | "ambiguous_input";
        };
        /** EquipmentModelListResponse */
        EquipmentModelListResponse: {
            /** Items */
            items: components["schemas"]["EquipmentModelResponse"][];
            pagination: components["schemas"]["PaginationMetadata"];
        };
        /** EquipmentModelResponse */
        EquipmentModelResponse: {
            /**
             * Catalog Release Id
             * Format: uuid
             */
            catalog_release_id: string;
            /** Code */
            code: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * EquipmentOperationalStatus
         * @description The current condition of an individually deployed equipment unit.
         * @enum {string}
         */
        EquipmentOperationalStatus: "operational" | "degraded" | "offline" | "maintenance";
        /** EquipmentUnitListResponse */
        EquipmentUnitListResponse: {
            /** Items */
            items: components["schemas"]["EquipmentUnitResponse"][];
            pagination: components["schemas"]["PaginationMetadata"];
        };
        /** EquipmentUnitResponse */
        EquipmentUnitResponse: {
            /** Asset Tag */
            asset_tag: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Equipment Model Id
             * Format: uuid
             */
            equipment_model_id: string;
            /**
             * Facility Id
             * Format: uuid
             */
            facility_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            operational_status: components["schemas"]["EquipmentOperationalStatus"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** EvidencePage[CompatibleStockEvidence] */
        EvidencePage_CompatibleStockEvidence_: {
            /**
             * Limit
             * @default 50
             */
            limit: number;
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /** Rows */
            rows: components["schemas"]["CompatibleStockEvidence"][];
            /** Total */
            total: number;
        };
        /** EvidencePage[FacilityEquipmentEvidence] */
        EvidencePage_FacilityEquipmentEvidence_: {
            /**
             * Limit
             * @default 50
             */
            limit: number;
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /** Rows */
            rows: components["schemas"]["FacilityEquipmentEvidence"][];
            /** Total */
            total: number;
        };
        /** EvidencePage[IncidentEvidence] */
        EvidencePage_IncidentEvidence_: {
            /**
             * Limit
             * @default 50
             */
            limit: number;
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /** Rows */
            rows: components["schemas"]["IncidentEvidence"][];
            /** Total */
            total: number;
        };
        /** EvidencePage[InventoryEvidence] */
        EvidencePage_InventoryEvidence_: {
            /**
             * Limit
             * @default 50
             */
            limit: number;
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /** Rows */
            rows: components["schemas"]["InventoryEvidence"][];
            /** Total */
            total: number;
        };
        /** EvidencePage[WorkOrderEvidence] */
        EvidencePage_WorkOrderEvidence_: {
            /**
             * Limit
             * @default 50
             */
            limit: number;
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /** Rows */
            rows: components["schemas"]["WorkOrderEvidence"][];
            /** Total */
            total: number;
        };
        /** FacilityEquipmentEvidence */
        FacilityEquipmentEvidence: {
            /** Facility Code */
            facility_code?: string | null;
            /**
             * Facility Id
             * Format: uuid
             */
            facility_id: string;
            /** Facility Name */
            facility_name?: string | null;
            /** Incidents */
            incidents: components["schemas"]["UnitIncidentEvidence"][];
            /** Units */
            units: components["schemas"]["UnitEvidence"][];
        };
        /** FacilityEquipmentPlan */
        FacilityEquipmentPlan: {
            /** Equipment Model Id */
            equipment_model_id?: string | null;
            facility?: components["schemas"]["FacilityFilter"];
            /** Incident Statuses */
            incident_statuses?: components["schemas"]["IncidentStatus"][] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "facility_equipment";
            /** Unit Statuses */
            unit_statuses?: components["schemas"]["EquipmentOperationalStatus"][] | null;
        };
        /** FacilityEquipmentResult */
        FacilityEquipmentResult: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "facility_equipment";
            page: components["schemas"]["EvidencePage_FacilityEquipmentEvidence_"];
        };
        /**
         * FacilityFilter
         * @description All supplied selectors intersect; location is an exact stored value.
         */
        FacilityFilter: {
            /** Facility Id */
            facility_id?: string | null;
            /** @description Select all facilities of this type; no individual facility ID is needed. */
            facility_type?: components["schemas"]["FacilityType"] | null;
            /** Location */
            location?: string | null;
        };
        /**
         * FacilityListResponse
         * @description A page of Facilities and its pagination metadata.
         */
        FacilityListResponse: {
            /** Items */
            items: components["schemas"]["FacilityResponse"][];
            pagination: components["schemas"]["PaginationMetadata"];
        };
        /**
         * FacilityOperationalStatus
         * @enum {string}
         */
        FacilityOperationalStatus: "operational" | "degraded" | "offline";
        /**
         * FacilityResponse
         * @description Public representation of a Facility record.
         */
        FacilityResponse: {
            /**
             * Body Or System
             * @description Stored celestial body or system context, e.g. Earth’s Moon or Earth–Moon system. Null means unspecified; not inferred from facility type.
             */
            body_or_system?: string | null;
            /** Code */
            code: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            facility_type: components["schemas"]["FacilityType"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Location */
            location: string;
            /** Name */
            name: string;
            operational_status: components["schemas"]["FacilityOperationalStatus"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * FacilityType
         * @enum {string}
         */
        FacilityType: "lunar_installation" | "orbital_station" | "logistics_depot" | "mission_control_center";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        /** IncidentEvidence */
        IncidentEvidence: {
            /** Asset Tag */
            asset_tag?: string | null;
            /** Facility Code */
            facility_code?: string | null;
            /**
             * Facility Id
             * Format: uuid
             */
            facility_id: string;
            /** Facility Name */
            facility_name?: string | null;
            /** Fault Code */
            fault_code: string | null;
            /**
             * Incident Id
             * Format: uuid
             */
            incident_id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Reference Code */
            reference_code?: string | null;
            severity: components["schemas"]["IncidentSeverity"];
            status: components["schemas"]["IncidentStatus"];
            /** Unit Id */
            unit_id: string | null;
        };
        /** IncidentListResponse */
        IncidentListResponse: {
            /** Items */
            items: components["schemas"]["IncidentResponse"][];
            pagination: components["schemas"]["PaginationMetadata"];
        };
        /** IncidentResponse */
        IncidentResponse: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Equipment Unit Id */
            equipment_unit_id: string | null;
            /**
             * Facility Id
             * Format: uuid
             */
            facility_id: string;
            /** Fault Code */
            fault_code: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            /** Reference Code */
            reference_code: string;
            /** Resolved At */
            resolved_at: string | null;
            severity: components["schemas"]["IncidentSeverity"];
            status: components["schemas"]["IncidentStatus"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * IncidentSeverity
         * @description The operational impact assigned to an incident.
         * @enum {string}
         */
        IncidentSeverity: "low" | "medium" | "high" | "critical";
        /**
         * IncidentStatus
         * @description The current lifecycle state of an incident.
         * @enum {string}
         */
        IncidentStatus: "open" | "investigating" | "resolved";
        /** IncidentsPlan */
        IncidentsPlan: {
            /** Equipment Model Id */
            equipment_model_id?: string | null;
            /** Equipment Unit Id */
            equipment_unit_id?: string | null;
            facility?: components["schemas"]["FacilityFilter"];
            /** Fault Code */
            fault_code?: string | null;
            occurred?: components["schemas"]["TimeWindow"] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "incidents";
            /** Severities */
            severities?: components["schemas"]["IncidentSeverity"][] | null;
            /** Statuses */
            statuses?: components["schemas"]["IncidentStatus"][] | null;
        };
        /** IncidentsResult */
        IncidentsResult: {
            /** Count */
            count: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "incidents";
            page: components["schemas"]["EvidencePage_IncidentEvidence_"];
        };
        /** InventoryEvidence */
        InventoryEvidence: {
            /** Component Code */
            component_code?: string | null;
            /**
             * Component Id
             * Format: uuid
             */
            component_id: string;
            /** Component Name */
            component_name?: string | null;
            /** Facility Code */
            facility_code?: string | null;
            /**
             * Facility Id
             * Format: uuid
             */
            facility_id: string;
            /** Facility Name */
            facility_name?: string | null;
            /**
             * Inventory Id
             * Format: uuid
             */
            inventory_id: string;
            /** Quantity On Hand */
            quantity_on_hand: number;
            /** Reorder Point */
            reorder_point: number;
            /** Shortfall */
            shortfall: number;
        };
        /** InventoryItemListResponse */
        InventoryItemListResponse: {
            /** Items */
            items: components["schemas"]["InventoryItemResponse"][];
            pagination: components["schemas"]["PaginationMetadata"];
        };
        /** InventoryItemResponse */
        InventoryItemResponse: {
            /**
             * Component Id
             * Format: uuid
             */
            component_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Facility Id
             * Format: uuid
             */
            facility_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Quantity On Hand */
            quantity_on_hand: number;
            /** Reorder Point */
            reorder_point: number;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** InventoryPlan */
        InventoryPlan: {
            /** Below Reorder Point */
            below_reorder_point?: boolean | null;
            /** Compatible Model Id */
            compatible_model_id?: string | null;
            /** Component Id */
            component_id?: string | null;
            facility?: components["schemas"]["FacilityFilter"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "inventory";
            quantity?: components["schemas"]["QuantityFilter"] | null;
        };
        /** InventoryResult */
        InventoryResult: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "inventory";
            page: components["schemas"]["EvidencePage_InventoryEvidence_"];
        };
        /**
         * PaginationMetadata
         * @description Pagination state returned with a collection response.
         */
        PaginationMetadata: {
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** PendingConfirmation */
        PendingConfirmation: {
            /** Confirmation Id */
            confirmation_id: string;
            /** Expires In Seconds */
            expires_in_seconds: number;
        };
        /** QuantityFilter */
        QuantityFilter: {
            /**
             * Operator
             * @description Comparison against quantity_on_hand: lt means <, lte <=, eq =, gte >=, gt >. Quantities are integers >= 0. Any complete set {0, ..., N} is exactly lte N (equivalently lt N+1), including when expressed as alternatives in ordinary language.
             * @enum {string}
             */
            operator: "lt" | "lte" | "eq" | "gte" | "gt";
            /**
             * Value
             * @description The integer bound, not a component count or reorder point.
             */
            value: number;
        };
        /**
         * QueryPageRequest
         * @description Caller-owned bounds matching the existing API's 50/100 limit convention.
         */
        QueryPageRequest: {
            /**
             * Limit
             * @default 50
             */
            limit: number;
            /**
             * Offset
             * @default 0
             */
            offset: number;
        };
        /** QuestionRequest */
        QuestionRequest: {
            page?: components["schemas"]["QueryPageRequest"];
            /** Question */
            question: string;
        };
        /** QuestionResponse */
        QuestionResponse: {
            confirmation?: components["schemas"]["PendingConfirmation"] | null;
            /** Evidence */
            evidence: (components["schemas"]["FacilityEquipmentResult"] | components["schemas"]["CompatibleStockResult"] | components["schemas"]["WorkOrdersResult"] | components["schemas"]["IncidentsResult"] | components["schemas"]["InventoryResult"]) | null;
            /** Outcome */
            outcome: components["schemas"]["Answered"] | components["schemas"]["CautiousAnswer"];
            page: components["schemas"]["QueryPageRequest"];
            /** Plan */
            plan: components["schemas"]["FacilityEquipmentPlan"] | components["schemas"]["CompatibleStockPlan"] | components["schemas"]["WorkOrdersPlan"] | components["schemas"]["IncidentsPlan"] | components["schemas"]["InventoryPlan"] | components["schemas"]["DeclinedPlan"];
            /**
             * Query Operation Id
             * Format: uuid
             */
            query_operation_id: string;
            /**
             * Request Id
             * Format: uuid
             */
            request_id: string;
            /**
             * Scope Status
             * @enum {string}
             */
            scope_status: "not_required" | "awaiting_confirmation" | "confirmed";
            /**
             * Synthesis Operation Id
             * Format: uuid
             */
            synthesis_operation_id: string;
        };
        /** RecordReference */
        RecordReference: {
            /**
             * Entity
             * @enum {string}
             */
            entity: "facility" | "equipment_unit" | "equipment_model" | "component" | "inventory" | "incident" | "work_order";
            /**
             * Record Id
             * Format: uuid
             */
            record_id: string;
        };
        /**
         * RenderedAnswer
         * @description Application output only. The renderer never accepts this as input.
         */
        RenderedAnswer: {
            /** References */
            references: components["schemas"]["RecordReference"][];
            /** Text */
            text: string;
        };
        /** TimeWindow */
        TimeWindow: {
            /**
             * End
             * Format: date-time
             */
            end: string;
            /**
             * Start
             * Format: date-time
             */
            start: string;
        };
        /** UnitEvidence */
        UnitEvidence: {
            /** Asset Tag */
            asset_tag?: string | null;
            operational_status: components["schemas"]["EquipmentOperationalStatus"];
            /**
             * Unit Id
             * Format: uuid
             */
            unit_id: string;
        };
        /** UnitIncidentEvidence */
        UnitIncidentEvidence: {
            /**
             * Equipment Unit Id
             * Format: uuid
             */
            equipment_unit_id: string;
            /**
             * Incident Id
             * Format: uuid
             */
            incident_id: string;
            /** Reference Code */
            reference_code?: string | null;
            status: components["schemas"]["IncidentStatus"];
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** WorkOrderEvidence */
        WorkOrderEvidence: {
            /** Blocked */
            blocked: boolean;
            /** Due At */
            due_at: string | null;
            /** Facility Code */
            facility_code?: string | null;
            /**
             * Facility Id
             * Format: uuid
             */
            facility_id: string;
            /** Facility Name */
            facility_name?: string | null;
            /** Incident Equipment Asset Tag */
            incident_equipment_asset_tag?: string | null;
            /** Incident Equipment Unit Id */
            incident_equipment_unit_id: string | null;
            /** Originating Incident Code */
            originating_incident_code?: string | null;
            /** Originating Incident Id */
            originating_incident_id: string | null;
            /** Overdue */
            overdue: boolean;
            priority: components["schemas"]["WorkOrderPriority"];
            /** Reference Code */
            reference_code?: string | null;
            status: components["schemas"]["WorkOrderStatus"];
            /** Target Equipment Asset Tag */
            target_equipment_asset_tag?: string | null;
            /** Target Equipment Unit Id */
            target_equipment_unit_id: string | null;
            /**
             * Work Order Id
             * Format: uuid
             */
            work_order_id: string;
        };
        /** WorkOrderListResponse */
        WorkOrderListResponse: {
            /** Items */
            items: components["schemas"]["WorkOrderResponse"][];
            pagination: components["schemas"]["PaginationMetadata"];
        };
        /**
         * WorkOrderPriority
         * @enum {string}
         */
        WorkOrderPriority: "low" | "medium" | "high" | "critical";
        /** WorkOrderResponse */
        WorkOrderResponse: {
            /** Completed At */
            completed_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Due At */
            due_at: string | null;
            /**
             * Facility Id
             * Format: uuid
             */
            facility_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Originating Incident Id
             * @description Incident that initiated this work; its affected unit may differ from the work target.
             */
            originating_incident_id: string | null;
            priority: components["schemas"]["WorkOrderPriority"];
            /** Reference Code */
            reference_code: string;
            status: components["schemas"]["WorkOrderStatus"];
            /**
             * Target Equipment Unit Id
             * @description Unit targeted by the work, independently of the originating incident; null permits facility-level work.
             */
            target_equipment_unit_id: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * WorkOrderStatus
         * @enum {string}
         */
        WorkOrderStatus: "open" | "in_progress" | "blocked" | "completed" | "cancelled";
        /** WorkOrdersPlan */
        WorkOrdersPlan: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            facility?: components["schemas"]["FacilityFilter"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "work_orders";
            /** Originating Incident Id */
            originating_incident_id?: string | null;
            /** Overdue */
            overdue?: boolean | null;
            /** Priorities */
            priorities?: components["schemas"]["WorkOrderPriority"][] | null;
            /** Statuses */
            statuses?: components["schemas"]["WorkOrderStatus"][] | null;
            /** Target Equipment Unit Id */
            target_equipment_unit_id?: string | null;
        };
        /** WorkOrdersResult */
        WorkOrdersResult: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            operation: "work_orders";
            page: components["schemas"]["EvidencePage_WorkOrderEvidence_"];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listComponents: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
                /** @description Exact catalog release. Omit to browse all releases; no latest-release selection. */
                catalog_release_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ComponentListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    getComponent: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                component_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ComponentResponse"];
                };
            };
            /** @description Shared catalog record not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    listEquipmentModels: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
                /** @description Exact catalog release. Omit to browse all releases; no latest-release selection. */
                catalog_release_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EquipmentModelListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    getEquipmentModel: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                equipment_model_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EquipmentModelResponse"];
                };
            };
            /** @description Shared catalog record not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    listCompatibleComponents: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                equipment_model_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ComponentListResponse"];
                };
            };
            /** @description Shared catalog record not found. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    listEquipmentUnits: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
                facility_id?: string | null;
                equipment_model_id?: string | null;
                operational_status?: components["schemas"]["EquipmentOperationalStatus"] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EquipmentUnitListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    getEquipmentUnit: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                equipment_unit_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EquipmentUnitResponse"];
                };
            };
            /** @description Record not found in the configured workspace. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    listFacilities: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FacilityListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    getFacility: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FacilityResponse"];
                };
            };
            /** @description Facility not found in the configured workspace. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    getHealth: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    listIncidents: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
                facility_id?: string | null;
                equipment_unit_id?: string | null;
                status?: components["schemas"]["IncidentStatus"] | null;
                /** @description Exact fault classification, trimmed and uppercased; unclassified incidents do not match. */
                fault_code?: string | null;
                /** @description Inclusive occurrence-time lower bound; timezone required. */
                occurred_from?: string | null;
                /** @description Exclusive occurrence-time upper bound; timezone required, later than occurred_from when both are supplied. */
                occurred_before?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    getIncident: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentResponse"];
                };
            };
            /** @description Record not found in the configured workspace. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    listInventoryItems: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
                facility_id?: string | null;
                component_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InventoryItemListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    getInventoryItem: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                inventory_item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InventoryItemResponse"];
                };
            };
            /** @description Record not found in the configured workspace. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    askQuestion: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QuestionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QuestionResponse"];
                };
            };
            /** @description Query exceeds execution limits. */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Referenced record or pending confirmation unavailable. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Unexpected question failure. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Invalid model query proposal. */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Model, database, configuration, or pending capacity unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Query execution timed out. */
            504: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    confirmQuestionScope: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConfirmationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QuestionResponse"];
                };
            };
            /** @description Query exceeds execution limits. */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Referenced record or pending confirmation unavailable. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Unexpected question failure. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Invalid model query proposal. */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Model, database, configuration, or pending capacity unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Query execution timed out. */
            504: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    listWorkOrders: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
                facility_id?: string | null;
                status?: components["schemas"]["WorkOrderStatus"] | null;
                priority?: components["schemas"]["WorkOrderPriority"] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkOrderListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
    getWorkOrder: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                work_order_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkOrderResponse"];
                };
            };
            /** @description Record not found in the configured workspace. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Database or workspace configuration unavailable. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/problem+json": {
                        /** Detail */
                        detail: string;
                        /** Instance */
                        instance?: string | null;
                        /** Status */
                        status: number;
                        /** Title */
                        title: string;
                        /**
                         * Type
                         * @default about:blank
                         */
                        type: string;
                    };
                };
            };
        };
    };
}
