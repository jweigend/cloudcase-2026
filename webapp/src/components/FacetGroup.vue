<template>
  <div class="border-b border-gray-200 pb-2">
    <!-- Klickbarer Header zum Auf-/Zuklappen -->
    <button 
      @click="toggleExpanded"
      class="w-full flex items-center justify-between text-sm font-medium text-gray-500 mb-1 hover:text-gray-700 transition-colors"
    >
      <span class="flex items-center gap-1">
        {{ title }}
        <span v-if="activeCount > 0" class="ml-1 px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
          {{ activeCount }}
        </span>
      </span>
      <svg 
        class="w-4 h-4 transition-transform duration-200" 
        :class="{ 'rotate-180': expanded }"
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
      </svg>
    </button>
    
    <!-- Aufklappbarer Inhalt -->
    <transition
      enter-active-class="transition-all duration-200 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 max-h-0"
      enter-to-class="opacity-100 max-h-96"
      leave-from-class="opacity-100 max-h-96"
      leave-to-class="opacity-0 max-h-0"
    >
      <ul v-show="expanded" class="space-y-0.5 overflow-hidden">
        <li 
          v-for="item in sortedItems" 
          :key="item.value"
          @click="$emit('toggle', item.value)"
          class="flex items-center justify-between px-2 py-1 rounded cursor-pointer transition-colors text-sm"
          :class="isActive(item.value) 
            ? 'bg-blue-100 text-blue-800 font-medium' 
            : 'hover:bg-gray-100 text-gray-700'"
        >
          <span class="flex items-center gap-1.5">
            <span 
              class="w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0"
              :class="isActive(item.value) ? 'bg-blue-600 border-blue-600' : 'border-gray-300'"
            >
              <svg v-if="isActive(item.value)" class="w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
              </svg>
            </span>
            <span>{{ formatter ? formatter(item.value) : item.value }}</span>
          </span>
          <span class="text-xs text-gray-500 tabular-nums">
            {{ formatCount(item.count) }}
          </span>
        </li>
      </ul>
    </transition>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  field: { type: String, required: true },
  items: { type: Array, default: () => [] },
  activeFilters: { type: Array, default: () => [] },
  formatter: { type: Function, default: null },
  expanded: { type: Boolean, default: false }
})

const emit = defineEmits(['toggle', 'update:expanded'])

// Items nach Anzahl sortiert (absteigend)
const sortedItems = computed(() => {
  return [...props.items].sort((a, b) => b.count - a.count)
})

// Anzahl aktiver Filter in dieser Gruppe
const activeCount = computed(() => {
  return props.items.filter(item => isActive(item.value)).length
})

// Toggle expanded state und emit an Parent
function toggleExpanded() {
  emit('update:expanded', !props.expanded)
}

function isActive(value) {
  return props.activeFilters.includes(`${props.field}:${value}`)
}

function formatCount(count) {
  if (count >= 1000000) {
    return (count / 1000000).toFixed(1) + 'M'
  }
  if (count >= 1000) {
    return (count / 1000).toFixed(0) + 'k'
  }
  return count.toLocaleString('de-DE')
}
</script>
