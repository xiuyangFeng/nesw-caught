import type { IChartApi } from 'lightweight-charts';
import { onBeforeUnmount, onMounted, type Ref } from 'vue';

type ChartContainerPair = {
  container: Ref<HTMLElement | null>;
  getChart: () => IChartApi | null;
};

function resizeChart(container: HTMLElement | null, chart: IChartApi | null) {
  if (!container || !chart) {
    return;
  }
  const { clientWidth, clientHeight } = container;
  if (clientWidth > 0 && clientHeight > 0) {
    chart.resize(clientWidth, clientHeight);
  }
}

export function useChartResize(pairs: ChartContainerPair[]) {
  let resizeObserver: ResizeObserver | null = null;

  function resizeAll() {
    for (const pair of pairs) {
      resizeChart(pair.container.value, pair.getChart());
    }
  }

  onMounted(() => {
    window.addEventListener('resize', resizeAll);

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => resizeAll());
      for (const pair of pairs) {
        if (pair.container.value) {
          resizeObserver.observe(pair.container.value);
        }
      }
    }
  });

  onBeforeUnmount(() => {
    window.removeEventListener('resize', resizeAll);
    resizeObserver?.disconnect();
    resizeObserver = null;
  });

  return { resizeAll };
}
