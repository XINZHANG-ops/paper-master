var canvas = document.getElementById('the-canvas');
var canvasBounds = canvas.getBoundingClientRect();


window.addEventListener('wheel', function(e) {
    // Check if the event happens within the current page
    if (
        e.clientX < currentPageInfo.left ||
        e.clientX > currentPageInfo.left + currentPageInfo.width ||
        e.clientY < currentPageInfo.top ||
        e.clientY > currentPageInfo.top + currentPageInfo.height
    ) {
        return;
    }

    // Prevent the default scrolling behavior
    e.preventDefault();

    if (e.deltaY < 0) {
        onPrevPage();
    } else {
        onNextPage();
    }
}, { passive: false });  // 添加这个选项来设置为被动模式


var pdfDoc = null,
    pageNum = 1,
    pageRendering = false,
    pageNumPending = null,
    scale = 1.0,
    canvas = document.getElementById('the-canvas'),
    ctx = canvas.getContext('2d');

let currentPageInfo = {};  // 存储当前页面的信息

function renderPage(num) {
  pageRendering = true;
  pdfDoc.getPage(num).then(function(page) {
    var viewport = page.getViewport({scale: scale});
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    var renderContext = {
      canvasContext: ctx,
      viewport: viewport
    };

    // Store page info
    currentPageInfo = {
      width: viewport.width,
      height: viewport.height,
      left: canvas.offsetLeft,
      top: canvas.offsetTop
    };

    var renderTask = page.render(renderContext);
    renderTask.promise.then(function () {
      pageRendering = false;
      if (pageNumPending !== null) {
        renderPage(pageNumPending);
        pageNumPending = null;
      }
    });
    // 更新chunks
    updateChunks(num);
    // 加载笔记
    onPageChange(num);
  });

  // Update page counters
  document.getElementById('page_num').textContent = num;
}


function queueRenderPage(num) {
  if (pageRendering) {
    pageNumPending = num;
  } else {
    renderPage(num);
  }
}

function onPrevPage() {
  if (pageNum <= 1) {
    return;
  }
  pageNum--;
  queueRenderPage(pageNum);
}

function onNextPage() {
  if (pageNum >= pdfDoc.numPages) {
    return;
  }
  pageNum++;
  queueRenderPage(pageNum);
}

function initPDFViewer(file) {
  var loadingTask = pdfjsLib.getDocument(file);
  loadingTask.promise.then(function(pdf) {
    pdfDoc = pdf;
    document.getElementById('prev').addEventListener('click', onPrevPage);
    document.getElementById('next').addEventListener('click', onNextPage);
    renderPage(pageNum);
  });
}

function updateChunks(pageNum) {
  fetch(`/api/chunks/${pageNum}`).then(response => {
    if (response.ok) {
      response.json().then(data => {
        var chunksDiv = document.getElementById('chunks');
        chunksDiv.innerHTML = '';
        data.chunks.forEach(chunk => {
          var chunkDiv = document.createElement('div');
          chunkDiv.textContent = chunk.replace(/\n/g, '<br>');
          chunkDiv.style.margin = '0 5% 10% 2%'; //上、右、下、左
          chunkDiv.innerHTML = chunk.replace(/\n/g, '<br>');
          chunksDiv.appendChild(chunkDiv);
        });
      });
    }
  });
}


// 在用户翻页时加载笔记
function onPageChange(pageNum) {
    fetch(`/api/notes/${window.filename}/${pageNum}`)  // 使用服务器传过来的文件名
        .then(response => response.json())
        .then(data => {
            document.getElementById('note-textarea').value = data.note;
        });
}

// 在用户更改笔记时保存笔记
document.getElementById('note-textarea').addEventListener('change', function() {
    fetch(`/api/notes/${window.filename}/${pageNum}`, {  // 使用服务器传过来的文件名
        method: 'POST',
        body: new URLSearchParams({'note': this.value})
    });
});

function handleScroll(event) {
    event.stopPropagation(); // 阻止事件向上冒泡
}

function autoSaveNote() {
    var note = document.getElementById('note-textarea').value;
    saveNote(note);
}
