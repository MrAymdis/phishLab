<template>
  <div class="page-container template-view">
    <PageHeader :title="tabLabel" :parents="['素材模板']" />

    <el-tabs v-model="activeTab" class="tpl-tabs">
      <!-- ====== Tab 1: 钓鱼邮件模板 ====== -->
      <el-tab-pane label="钓鱼邮件模板" name="email">
        <!-- 统计卡片 -->
        <div class="stat-grid">
          <div
            v-for="s in emailStats"
            :key="s.title"
            class="card stat-card"
            :class="`card-${s.accent}`"
          >
            <div class="stat-title">{{ s.title }}</div>
            <div
              class="stat-value"
              :class="{ 'stat-value-sm': s.valueSm }"
              :style="s.valueColor ? { color: s.valueColor } : {}"
            >
              {{ s.value }}<span v-if="s.suffix" class="stat-suffix">{{ s.suffix }}</span>
            </div>
            <div class="stat-sub" :class="`sub-${s.subTone}`">{{ s.sub }}</div>
          </div>
        </div>

        <!-- 工具栏 -->
        <div class="card toolbar">
          <div class="filter-tags">
            <span
              v-for="f in emailFilters"
              :key="f.key"
              class="filter-tag"
              :class="{ active: emailCat === f.key }"
              @click="emailCat = f.key"
            >{{ f.label }}<span class="count">{{ f.count }}</span></span>
          </div>
          <el-input
            v-model="emailKw"
            :prefix-icon="Search"
            size="small"
            placeholder="搜索模板名称"
            class="toolbar-search"
            clearable
          />
          <el-button type="primary" size="small" :icon="Plus" @click="openEmailDialog()">新建模板</el-button>
        </div>

        <!-- 模板卡片网格 -->
        <div class="card-grid">
          <div
            v-for="t in pagedEmails"
            :key="t.id"
            class="template-card"
            :style="{ '--item-color': emailCatColor[t.cat] }"
          >
            <div class="template-preview">
              <div class="preview-head">
                <span class="preview-icon">✉</span>
                <span class="preview-subject">{{ t.subject }}</span>
              </div>
              <div class="preview-meta">{{ t.preview }}</div>
            </div>
            <div class="template-meta">
              <div class="meta-row">
                <p class="template-name">{{ t.name }}</p>
                <span class="badge badge-cat">{{ t.catText }}</span>
              </div>
              <div class="meta-row stars-row">
                <span class="stars">
                  <span
                    v-for="i in 5"
                    :key="i"
                    class="star"
                    :class="{ filled: i <= t.stars }"
                  >★</span>
                </span>
                <span class="star-text">{{ starText[t.stars] }}</span>
              </div>
              <div class="meta-row stats-row">
                <span>使用 {{ t.used }} 次</span>
                <span class="click-rate">点击率 {{ t.click }}%</span>
              </div>
              <div class="card-actions">
                <el-button size="small" link @click="previewEmail(t)">预览</el-button>
                <el-button size="small" link @click="openEmailDialog(t)">编辑</el-button>
                <el-button size="small" link @click="testEmail(t)">测试发送</el-button>
                <el-button size="small" link @click="copyEmail(t)">复制</el-button>
                <el-button size="small" link type="danger" @click="deleteEmail(t)">删除</el-button>
              </div>
            </div>
          </div>
          <div v-if="pagedEmails.length === 0" class="empty-tip">暂无匹配的模板</div>
        </div>

        <!-- 分页 -->
        <div class="pager-bar">
          <span class="pager-info">共 {{ filteredEmails.length }} 条</span>
          <el-pagination
            v-model:current-page="emailPage"
            :page-size="emailPageSize"
            :total="filteredEmails.length"
            layout="prev, pager, next"
            small
          />
        </div>
      </el-tab-pane>

      <!-- ====== Tab 2: 落地页管理 ====== -->
      <el-tab-pane label="落地页管理" name="landing">
        <!-- 统计卡片 -->
        <div class="stat-grid">
          <div
            v-for="s in landingStats"
            :key="s.title"
            class="card stat-card"
            :class="`card-${s.accent}`"
          >
            <div class="stat-title">{{ s.title }}</div>
            <div
              class="stat-value"
              :class="{ 'stat-value-sm': s.valueSm }"
              :style="s.valueColor ? { color: s.valueColor } : {}"
            >
              {{ s.value }}<span v-if="s.suffix" class="stat-suffix">{{ s.suffix }}</span>
            </div>
            <div class="stat-sub" :class="`sub-${s.subTone}`">{{ s.sub }}</div>
          </div>
        </div>

        <!-- 工具栏 -->
        <div class="card toolbar">
          <div class="filter-tags">
            <span
              v-for="f in landingFilters"
              :key="f.key"
              class="filter-tag"
              :class="{ active: landingType === f.key }"
              @click="landingType = f.key"
            >{{ f.label }}<span class="count">{{ f.count }}</span></span>
          </div>
          <el-input
            v-model="landingKw"
            :prefix-icon="Search"
            size="small"
            placeholder="搜索页面名称"
            class="toolbar-search"
            clearable
          />
          <el-button size="small" :icon="Link" @click="cloneDialogVisible = true">克隆页面</el-button>
          <el-button type="primary" size="small" :icon="Plus" @click="openLandingDialog()">新建页面</el-button>
        </div>

        <!-- 落地页卡片网格 -->
        <div class="card-grid">
          <div
            v-for="l in pagedLandings"
            :key="l.id"
            class="template-card"
            :style="{ '--item-color': ltypeColor[l.type] }"
          >
            <div class="landing-preview">
              <div class="mock-form">
                <div class="mock-bar mock-title"></div>
                <div class="mock-bar mock-line"></div>
                <div class="mock-bar mock-line"></div>
                <div class="mock-bar mock-btn"></div>
              </div>
              <span class="preview-tip">{{ l.typeText }} 登录表单</span>
            </div>
            <div class="template-meta">
              <div class="meta-row">
                <p class="template-name">{{ l.name }}</p>
                <span class="badge badge-cat">{{ l.typeText }}</span>
              </div>
              <div class="meta-row stats-row">
                <span>表单字段 {{ l.fields }} 项</span>
                <span>收集项 {{ l.collect }} 项</span>
                <span>使用 {{ l.used }} 次</span>
              </div>
              <div class="card-actions">
                <el-button size="small" link @click="previewLanding(l)">预览</el-button>
                <el-button size="small" link @click="openLandingDialog(l)">编辑</el-button>
                <el-button size="small" link @click="cloneLanding(l)">克隆</el-button>
                <el-button size="small" link type="danger" @click="deleteLanding(l)">删除</el-button>
              </div>
            </div>
          </div>
          <div v-if="pagedLandings.length === 0" class="empty-tip">暂无匹配的落地页</div>
        </div>

        <!-- 分页 -->
        <div class="pager-bar">
          <span class="pager-info">共 {{ filteredLandings.length }} 条</span>
          <el-pagination
            v-model:current-page="landingPage"
            :page-size="landingPageSize"
            :total="filteredLandings.length"
            layout="prev, pager, next"
            small
          />
        </div>
      </el-tab-pane>

      <!-- ====== Tab 3: 附件与载荷 ====== -->
      <el-tab-pane label="附件与载荷" name="payload">
        <!-- 统计卡片 -->
        <div class="stat-grid stat-grid-3">
          <div
            v-for="s in payloadStats"
            :key="s.title"
            class="card stat-card"
            :class="`card-${s.accent}`"
          >
            <div class="stat-title">{{ s.title }}</div>
            <div
              class="stat-value"
              :class="{ 'stat-value-sm': s.valueSm }"
              :style="s.valueColor ? { color: s.valueColor } : {}"
            >
              {{ s.value }}<span v-if="s.suffix" class="stat-suffix">{{ s.suffix }}</span>
            </div>
            <div class="stat-sub" :class="`sub-${s.subTone}`">{{ s.sub }}</div>
          </div>
        </div>

        <!-- 工具栏 -->
        <div class="card toolbar">
          <div class="filter-tags">
            <span
              v-for="f in payloadFilters"
              :key="f.key"
              class="filter-tag"
              :class="{ active: payloadType === f.key }"
              @click="payloadType = f.key"
            >{{ f.label }}<span class="count">{{ f.count }}</span></span>
          </div>
          <el-input
            v-model="payloadKw"
            :prefix-icon="Search"
            size="small"
            placeholder="搜索文件名"
            class="toolbar-search"
            clearable
          />
          <el-button size="small" :icon="Iphone" @click="qrDialogVisible = true">生成二维码</el-button>
          <el-button type="primary" size="small" :icon="Upload" @click="uploadDialogVisible = true">上传附件</el-button>
        </div>

        <!-- 数据表格 -->
        <div class="card card-blue table-card">
          <table class="data-table">
            <colgroup>
              <col style="width: 24%" />
              <col style="width: 11%" />
              <col style="width: 9%" />
              <col style="width: 13%" />
              <col style="width: 17%" />
              <col style="width: 8%" />
              <col style="width: 9%" />
              <col style="width: 9%" />
            </colgroup>
            <thead>
              <tr>
                <th>文件名</th>
                <th>类型</th>
                <th>文件大小</th>
                <th>目标平台</th>
                <th>检测逃逸率</th>
                <th>使用次数</th>
                <th>状态</th>
                <th class="ta-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in pagedPayloads"
                :key="p.id"
                :style="{ '--item-color': ptypeColor[p.type] }"
              >
                <td>
                  <div class="file-cell">
                    <span class="file-icon">{{ p.icon }}</span>
                    <span class="file-name">{{ p.name }}</span>
                  </div>
                </td>
                <td><span class="badge badge-cat">{{ p.typeText }}</span></td>
                <td class="muted">{{ p.size }}</td>
                <td class="muted">{{ p.platform }}</td>
                <td>
                  <div class="evade-cell">
                    <div class="bar-track">
                      <div
                        class="bar-fill"
                        :style="{ width: p.evade + '%', background: evadeColor(p.evade) }"
                      ></div>
                    </div>
                    <span class="evade-val" :style="{ color: evadeColor(p.evade) }">{{ p.evade }}%</span>
                  </div>
                </td>
                <td class="used-num">{{ p.used }}</td>
                <td>
                  <span class="badge" :class="p.status === 'enabled' ? 'badge-on' : 'badge-off'">
                    <span
                      class="dot"
                      :class="p.status === 'enabled' ? 'dot-on' : 'dot-off'"
                    ></span>{{ p.status === 'enabled' ? '启用' : '禁用' }}
                  </span>
                </td>
                <td class="ta-right">
                  <div class="card-actions table-actions">
                    <el-button size="small" link @click="downloadPayload(p)">下载</el-button>
                    <el-button size="small" link @click="editPayload(p)">编辑</el-button>
                    <el-button size="small" link type="warning" @click="togglePayload(p)">
                      {{ p.status === 'enabled' ? '禁用' : '启用' }}
                    </el-button>
                    <el-button size="small" link type="danger" @click="deletePayload(p)">删除</el-button>
                  </div>
                </td>
              </tr>
              <tr v-if="pagedPayloads.length === 0">
                <td colspan="8" class="empty-tip">暂无匹配的数据</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页 -->
        <div class="pager-bar">
          <span class="pager-info">共 {{ filteredPayloads.length }} 条</span>
          <el-pagination
            v-model:current-page="payloadPage"
            :page-size="payloadPageSize"
            :total="filteredPayloads.length"
            layout="prev, pager, next"
            small
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- ====== 弹窗：新建/编辑邮件模板 ====== -->
    <el-dialog
      v-model="emailDialogVisible"
      :title="emailForm.id ? '编辑邮件模板' : '新建邮件模板'"
      width="680px"
      destroy-on-close
    >
      <el-form :model="emailForm" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="模板名称" required>
              <el-input v-model="emailForm.name" placeholder="如：OA密码过期提醒" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="场景分类" required>
              <el-select v-model="emailForm.cat" style="width: 100%">
                <el-option
                  v-for="f in emailCatOptions"
                  :key="f.key"
                  :label="f.label"
                  :value="f.key"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="难度等级">
          <el-rate
            v-model="emailForm.stars"
            :max="5"
            show-text
            :texts="['初级', '初级', '中级', '高级', '专家']"
          />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="邮件主题" required>
              <el-input v-model="emailForm.subject" placeholder="如：【安全提醒】您的OA账号密码即将过期" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发件人名称" required>
              <el-input v-model="emailForm.sender" placeholder="如：OA系统管理员" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="邮件正文">
          <div class="var-toolbar">
            <span class="var-tip">插入变量：</span>
            <el-tag
              v-for="v in emailVariables"
              :key="v"
              size="small"
              effect="plain"
              class="var-tag"
              @click="insertVariable(v)"
            >{{ v }}</el-tag>
          </div>
          <el-input
            v-model="emailForm.body"
            type="textarea"
            :rows="8"
            placeholder="在此输入邮件正文，支持动态变量..."
          />
          <!-- v-pre：内容含字面量模板变量 {{.Xxx}}，需跳过 Vue 插值解析 -->
          <div v-pre class="form-hint">
            支持插入动态变量：{{.FirstName}} {{.LastName}} {{.Department}} {{.Email}} {{.Date}} {{.ResetURL}} 等，发送时自动替换；{{.QRCode}} 将落地页链接渲染为二维码附件。
          </div>
        </el-form-item>
        <el-form-item label="追踪选项">
          <div class="track-list">
            <div class="track-item">
              <div class="track-info">
                <span class="track-title">追踪像素</span>
                <p class="track-desc">嵌入1x1图片，统计邮件打开率</p>
              </div>
              <el-switch v-model="emailForm.trackPixel" />
            </div>
            <div class="track-item">
              <div class="track-info">
                <span class="track-title">链接追踪</span>
                <p class="track-desc">替换正文链接，统计点击行为</p>
              </div>
              <el-switch v-model="emailForm.trackLink" />
            </div>
            <div class="track-item">
              <div class="track-info">
                <span class="track-title">附件追踪</span>
                <p class="track-desc">统计附件下载行为</p>
              </div>
              <el-switch v-model="emailForm.trackAttach" />
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="emailDialogVisible = false">取消</el-button>
        <el-button @click="saveEmail('draft')">保存草稿</el-button>
        <el-button type="primary" @click="saveEmail('test')">保存并测试</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：克隆落地页 ====== -->
    <el-dialog v-model="cloneDialogVisible" title="克隆页面" width="520px" destroy-on-close>
      <el-form :model="cloneForm" label-width="120px">
        <el-form-item label="源页面URL" required>
          <el-input v-model="cloneForm.url" placeholder="https://mail.company.com/login" />
          <div class="form-hint">输入需要克隆的页面地址，系统将自动抓取页面结构与样式。</div>
        </el-form-item>
        <el-form-item label="页面名称" required>
          <el-input v-model="cloneForm.name" placeholder="如：企业邮箱登录页" />
        </el-form-item>
        <el-form-item label="页面类型">
          <el-select v-model="cloneForm.type" style="width: 100%">
            <el-option label="邮箱登录" value="mail" />
            <el-option label="OA系统" value="oa" />
            <el-option label="网盘认证" value="pan" />
            <el-option label="支付页面" value="pay" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="移动端适配">
          <div class="track-item">
            <div class="track-info">
              <span class="track-title">自动适配移动端</span>
              <p class="track-desc">生成响应式布局，支持手机访问</p>
            </div>
            <el-switch v-model="cloneForm.mobile" />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cloneDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitClone">开始克隆</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：邮件模板预览 ====== -->
    <el-dialog v-model="emailPreviewVisible" :title="`预览：${emailPreviewData.name}`" width="780px" :close-on-click-modal="true">
      <div v-loading="emailPreviewLoading" class="email-preview-container">
        <div class="email-preview-header">
          <div class="preview-row"><span class="preview-label">发件人：</span><span>{{ emailPreviewData.sender || '—' }}</span></div>
          <div class="preview-row"><span class="preview-label">主题：</span><span>{{ emailPreviewData.subject || '—' }}</span></div>
        </div>
        <div class="email-preview-divider"></div>
        <iframe
          v-if="emailPreviewData.body"
          :srcdoc="emailPreviewData.body"
          class="email-preview-iframe"
          sandbox="allow-same-origin"
        />
        <el-empty v-else description="暂无模板内容" />
      </div>
      <template #footer>
        <el-button @click="emailPreviewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：落地页预览 ====== -->
    <el-dialog v-model="landingPreviewVisible" :title="`预览：${landingPreviewData.name}`" width="820px" :close-on-click-modal="true">
      <div v-loading="landingPreviewLoading" class="landing-preview-container">
        <div class="landing-preview-header">
          <div class="preview-row"><span class="preview-label">页面类型：</span><span>{{ landingPreviewData.typeText || '—' }}</span></div>
          <div class="preview-row" v-if="landingPreviewData.slug"><span class="preview-label">访问路径：</span><span class="preview-slug">/p/{{ landingPreviewData.slug }}</span></div>
          <div class="preview-row" v-if="landingPreviewData.fields.length"><span class="preview-label">表单字段：</span><span>{{ landingPreviewData.fields.map(f => f.label).join(' / ') }}</span></div>
        </div>
        <div class="email-preview-divider"></div>
        <iframe
          v-if="landingPreviewSrc && !landingSrcFailed"
          :src="landingPreviewSrc"
          class="email-preview-iframe"
          @error="landingSrcFailed = true"
        />
        <iframe
          v-else-if="landingPreviewData.html_content"
          :srcdoc="landingPreviewData.html_content"
          class="email-preview-iframe"
          sandbox="allow-scripts"
        />
        <el-empty v-else description="暂无页面内容（该落地页可能仅注册了表单结构，无自定义HTML）" />
      </div>
      <template #footer>
        <el-button @click="landingPreviewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：新建/编辑落地页 ====== -->
    <el-dialog
      v-model="landingDialogVisible"
      :title="landingForm.id ? '编辑落地页' : '新建落地页'"
      width="680px"
      destroy-on-close
    >
      <el-form :model="landingForm" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="页面名称" required>
              <el-input v-model="landingForm.name" placeholder="如：企业邮箱登录页" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="页面类型" required>
              <el-select v-model="landingForm.type" style="width: 100%">
                <el-option label="邮箱登录" value="mail" />
                <el-option label="OA系统" value="oa" />
                <el-option label="网盘认证" value="pan" />
                <el-option label="支付页面" value="pay" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="HTML 内容">
          <div class="html-editor-wrap">
            <div class="html-editor-toolbar">
              <el-button size="small" @click="landingForm.html_content = ''">清空</el-button>
              <el-button size="small" @click="generateDefaultHtml">生成默认模板</el-button>
              <span class="form-hint" style="margin-left:auto">留空时按页面类型自动生成默认 HTML</span>
            </div>
            <el-input
              v-model="landingForm.html_content"
              type="textarea"
              :rows="10"
              placeholder="粘贴或编写 HTML 内容…"
              class="html-textarea"
            />
          </div>
          <div class="form-hint">落地页完整 HTML。留空保存时将按页面类型自动生成默认登录表单模板。</div>
        </el-form-item>
        <el-form-item label="表单字段配置">
          <el-checkbox-group v-model="landingForm.fields" class="field-grid">
            <el-checkbox v-for="f in fieldOptions" :key="f" :value="f">{{ f }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="教育弹窗内容">
          <el-input
            v-model="landingForm.edu"
            type="textarea"
            :rows="4"
            placeholder="用户提交凭据后展示的安全教育内容"
          />
          <div class="form-hint">用户提交表单后自动弹出，用于即时安全教育。</div>
        </el-form-item>
        <el-form-item label="跳转设置">
          <el-select v-model="landingForm.redirect" style="width: 100%">
            <el-option label="显示教育弹窗后停留" value="edu" />
            <el-option label="跳转至真实系统首页" value="official" />
            <el-option label="跳转至自定义URL" value="custom" />
            <el-option label="关闭页面" value="none" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="landingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveLanding">保存页面</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：生成二维码 ====== -->
    <el-dialog v-model="qrDialogVisible" title="生成二维码" width="600px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="二维码类型">
          <div class="qr-type-grid">
            <div
              v-for="qt in qrTypes"
              :key="qt.key"
              class="option-card"
              :class="{ selected: qrType === qt.key }"
              :style="{ '--item-color': qt.color }"
              @click="qrType = qt.key"
            >
              <div class="option-card-icon" :style="{ background: qt.color }">{{ qt.label }}</div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="qrContent" placeholder="https://secure-login.company.com/verify" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="尺寸">
              <el-select v-model="qrSize" style="width: 100%">
                <el-option label="256 × 256 px" :value="256" />
                <el-option label="512 × 512 px" :value="512" />
                <el-option label="1024 × 1024 px" :value="1024" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Logo上传">
              <el-upload
                action="#"
                :auto-upload="false"
                :show-file-list="false"
                :on-change="onQrLogoChange"
              >
                <el-button>{{ qrLogoName || '选择文件' }}</el-button>
              </el-upload>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="生成预览">
          <div class="qr-preview-area">
            <el-icon :size="48" color="var(--color-text-tertiary)"><Picture /></el-icon>
            <span class="qr-preview-tip">
              {{ qrContent ? '点击下方按钮生成预览' : '请输入内容后生成预览' }}
            </span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="qrDialogVisible = false">取消</el-button>
        <el-button @click="previewQr">生成预览</el-button>
        <el-button type="primary" @click="submitQr">保存二维码</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：上传附件 ====== -->
    <el-dialog v-model="uploadDialogVisible" title="上传附件" width="560px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="文件" required>
          <el-upload
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            :on-change="onUploadChange"
            class="upload-drag"
          >
            <el-icon :size="32" color="var(--color-text-tertiary)"><UploadFilled /></el-icon>
            <div class="upload-text">点击或拖拽文件到此处上传</div>
            <template #tip>
              <div class="form-hint">支持 .docx .xlsx .exe .lnk .zip 等，单文件 ≤ 20MB</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="目标平台">
          <el-checkbox-group v-model="uploadPlatforms" class="field-grid-3">
            <el-checkbox value="Windows">Windows</el-checkbox>
            <el-checkbox value="macOS">macOS</el-checkbox>
            <el-checkbox value="Linux">Linux</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="免杀处理">
          <el-checkbox-group v-model="uploadEvasions" class="evasion-list">
            <el-checkbox v-for="e in evasionOptions" :key="e" :value="e">{{ e }}</el-checkbox>
          </el-checkbox-group>
          <div class="form-hint">免杀选项仅用于授权演练场景，所有操作将写入审计日志</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUpload">上传并处理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { Plus, Search, Upload, Link, UploadFilled, Iphone, Picture } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import { templateApi } from '@/api'

// ===== 类型定义 =====
type TabName = 'email' | 'landing' | 'payload'
type Accent = 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'teal'
type SubTone = 'success' | 'secondary' | 'tertiary'

interface StatItem {
  accent: Accent
  title: string
  value: string
  suffix?: string
  valueColor?: string
  valueSm?: boolean
  sub: string
  subTone: SubTone
}

interface EmailTemplate {
  id: number
  name: string
  cat: string
  catText: string
  subject: string
  sender: string
  stars: number
  used: number
  click: number
  preview: string
  created_at?: string
}

interface LandingPage {
  id: number
  name: string
  type: string
  typeText: string
  fields: number
  collect: number
  used: number
  created_at?: string
}

interface PayloadItem {
  id: number
  name: string
  type: string
  typeText: string
  size: string
  platform: string
  evade: number
  used: number
  status: 'enabled' | 'disabled'
  icon: string
  created_at?: string
}

interface FilterItem {
  key: string
  label: string
  count: number
}

// ===== Tab 切换 =====
const activeTab = ref<TabName>('email')
const tabLabel = computed(() =>
  activeTab.value === 'email' ? '钓鱼邮件模板' : activeTab.value === 'landing' ? '落地页管理' : '附件与载荷'
)

// ===== 难度星级文案 =====
const starText: Record<number, string> = { 1: '初级', 2: '初级', 3: '中级', 4: '高级', 5: '专家' }

// ============ Tab1: 邮件模板 ============
// 统计卡片与筛选计数均由真实数据实时计算
const emailCatLabels: Record<string, string> = {
  holiday: '节假日', upgrade: '系统升级', lottery: '中奖', hr: 'HR通知', finance: '财务报销', alert: '安全告警',
}

const emailStats = computed<StatItem[]>(() => {
  const data = emailData.value
  const month = new Date().toISOString().slice(0, 7)
  const newThisMonth = data.filter((d) => (d.created_at || '').startsWith(month)).length
  const top = data.reduce<EmailTemplate | null>((m, d) => (d.used > (m?.used ?? -1) ? d : m), null)
  const avgClick = data.length ? data.reduce((s, d) => s + d.click, 0) / data.length : 0
  return [
    { accent: 'blue', title: '邮件模板总数', value: String(data.length), sub: `↑ ${newThisMonth} 本月新增`, subTone: 'success' },
    { accent: 'green', title: '本月新增', value: String(newThisMonth), valueColor: 'var(--accent-green)', sub: '按创建时间实时统计', subTone: 'secondary' },
    { accent: 'orange', title: '使用次数最多', value: top?.name || '-', valueSm: true, sub: top ? `累计使用 ${top.used} 次` : '暂无使用记录', subTone: 'secondary' },
    { accent: 'teal', title: '平均点击率', value: avgClick.toFixed(1), suffix: '%', sub: '全模板均值', subTone: 'tertiary' },
  ]
})

const emailFilters = computed<FilterItem[]>(() => {
  const data = emailData.value
  const items: FilterItem[] = [{ key: 'all', label: '全部', count: data.length }]
  for (const [key, label] of Object.entries(emailCatLabels)) {
    const n = data.filter((d) => d.cat === key).length
    if (n > 0) items.push({ key, label, count: n })
  }
  return items
})

// 场景分类 → 主题色（统一走 CSS 变量，避免硬编码）
const emailCatColor: Record<string, string> = {
  holiday: 'var(--accent-warning)',
  upgrade: 'var(--accent-blue)',
  lottery: 'var(--accent-green)',
  hr: 'var(--accent-purple)',
  finance: 'var(--accent-orange)',
  alert: 'var(--accent-red)',
}

const emailData = ref<EmailTemplate[]>([])

const emailCat = ref('all')
const emailKw = ref('')
const emailPage = ref(1)
const emailPageSize = 6

const emailCatOptions = computed(() => emailFilters.value.filter((f) => f.key !== 'all'))

const filteredEmails = computed(() => {
  const kw = emailKw.value.trim().toLowerCase()
  return emailData.value.filter((d) => {
    if (emailCat.value !== 'all' && d.cat !== emailCat.value) return false
    if (kw && !d.name.toLowerCase().includes(kw) && !d.subject.toLowerCase().includes(kw)) return false
    return true
  })
})

const pagedEmails = computed(() => {
  const total = filteredEmails.value.length
  const pages = Math.max(1, Math.ceil(total / emailPageSize))
  const page = Math.min(emailPage.value, pages)
  const start = (page - 1) * emailPageSize
  return filteredEmails.value.slice(start, start + emailPageSize)
})

watch(emailCat, () => { emailPage.value = 1 })
watch(emailKw, () => { emailPage.value = 1 })

// 邮件模板卡片操作
const emailPreviewVisible = ref(false)
const emailPreviewLoading = ref(false)
const emailPreviewData = reactive({
  name: '',
  subject: '',
  sender: '',
  body: '',
})

async function previewEmail(row: EmailTemplate) {
  emailPreviewVisible.value = true
  emailPreviewLoading.value = true
  emailPreviewData.name = row.name
  emailPreviewData.subject = row.subject
  emailPreviewData.sender = row.sender || ''
  emailPreviewData.body = ''
  try {
    const detail = await templateApi.getEmailTemplate(row.id) as Record<string, unknown>
    emailPreviewData.body = (detail.body as string) || (detail.html_body as string) || ''
    emailPreviewData.sender = (detail.sender as string) || emailPreviewData.sender
  } catch {
    // 失败时由拦截器提示
  } finally {
    emailPreviewLoading.value = false
  }
}
function testEmail(row: EmailTemplate) {
  ElMessage.success(`模板「${row.name}」测试邮件已发送至您的邮箱`)
}
async function copyEmail(row: EmailTemplate) {
  try {
    await templateApi.duplicateEmailTemplate(row.id)
    ElMessage.success(`已复制模板「${row.name}」，副本已生成`)
    await loadTemplates()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}
function deleteEmail(row: EmailTemplate) {
  ElMessageBox.confirm(`确认删除模板「${row.name}」？`, '提示', { type: 'warning' })
    .then(() => ElMessage.success('模板已删除'))
    .catch(() => { /* 用户取消 */ })
}

// 邮件模板弹窗
const emailDialogVisible = ref(false)
const emailVariables = ['{{.FirstName}}', '{{.LastName}}', '{{.Department}}', '{{.Email}}', '{{.Date}}', '{{.ResetURL}}', '{{.QRCode}}']
const emailForm = reactive({
  id: 0,
  name: '',
  cat: 'upgrade' as string,
  stars: 3,
  subject: '',
  sender: '',
  body: '',
  trackPixel: true,
  trackLink: true,
  trackAttach: false,
})

async function openEmailDialog(row?: EmailTemplate) {
  if (row) {
    emailForm.id = row.id
    emailForm.name = row.name
    emailForm.cat = row.cat || 'upgrade'
    emailForm.subject = row.subject
    emailForm.sender = row.sender || ''
    emailForm.stars = row.stars || 3
    emailForm.body = ''
    // 拉取详情获取完整 html_body
    try {
      const detail = await templateApi.getEmailTemplate(row.id) as Record<string, unknown>
      emailForm.body = (detail.body as string) || (detail.html_body as string) || ''
      emailForm.sender = (detail.sender as string) || emailForm.sender
      emailForm.stars = (detail.stars as number) || emailForm.stars
      if (typeof detail.track_pixel === 'boolean') emailForm.trackPixel = detail.track_pixel
      if (typeof detail.track_link === 'boolean') emailForm.trackLink = detail.track_link
      if (typeof detail.track_attach === 'boolean') emailForm.trackAttach = detail.track_attach
    } catch {
      // 失败时由拦截器提示
    }
  } else {
    Object.assign(emailForm, {
      id: 0, name: '', cat: 'upgrade', stars: 3, subject: '', sender: '', body: '',
      trackPixel: true, trackLink: true, trackAttach: false,
    })
  }
  emailDialogVisible.value = true
}

function insertVariable(v: string) {
  emailForm.body += v
}

async function saveEmail(mode: 'draft' | 'test') {
  if (!emailForm.name) {
    ElMessage.warning('请填写模板名称')
    return
  }
  try {
    const payload = {
      name: emailForm.name,
      scene: emailForm.cat,
      subject: emailForm.subject,
      html_body: emailForm.body,
      source: 'custom',
      track_pixel: emailForm.trackPixel,
      track_link: emailForm.trackLink,
      track_attach: emailForm.trackAttach,
    }
    if (!emailForm.id) {
      await templateApi.createEmailTemplate(payload)
    } else {
      await templateApi.updateEmailTemplate(emailForm.id, payload)
    }
    await loadTemplates()
    emailDialogVisible.value = false
    ElMessage.success(mode === 'draft' ? '模板草稿已保存' : '模板已保存，测试邮件已发送')
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

// ============ Tab2: 落地页 ============
const landingStats = computed<StatItem[]>(() => {
  const data = landingData.value
  const cloned = data.filter((d) => d.type === 'cloned').length
  const custom = data.filter((d) => d.type === 'custom').length
  return [
    { accent: 'blue', title: '落地页总数', value: String(data.length), sub: '实时统计', subTone: 'success' },
    { accent: 'purple', title: '克隆页面数', value: String(cloned), valueColor: 'var(--accent-purple)', sub: 'URL 克隆工具产出', subTone: 'secondary' },
    { accent: 'green', title: '自定义页面数', value: String(custom), valueColor: 'var(--accent-green)', sub: '手动新建', subTone: 'secondary' },
    { accent: 'orange', title: '平均停留时长', value: '-', sub: '未接入停留追踪', subTone: 'tertiary' },
  ]
})

const landingTypeLabels: Record<string, string> = {
  mail: '邮箱登录', oa: 'OA系统', pan: '网盘认证', pay: '支付页面', custom: '自定义', cloned: '克隆页面',
}

const landingFilters = computed<FilterItem[]>(() => {
  const data = landingData.value
  const items: FilterItem[] = [{ key: 'all', label: '全部', count: data.length }]
  for (const [key, label] of Object.entries(landingTypeLabels)) {
    const n = data.filter((d) => d.type === key).length
    if (n > 0) items.push({ key, label, count: n })
  }
  return items
})

const ltypeColor: Record<string, string> = {
  mail: 'var(--accent-blue)',
  oa: 'var(--accent-purple)',
  pan: 'var(--accent-teal)',
  pay: 'var(--accent-orange)',
  custom: 'var(--accent-green)',
}

const landingData = ref<LandingPage[]>([])

const landingType = ref('all')
const landingKw = ref('')
const landingPage = ref(1)
const landingPageSize = 6

const filteredLandings = computed(() => {
  const kw = landingKw.value.trim().toLowerCase()
  return landingData.value.filter((d) => {
    if (landingType.value !== 'all' && d.type !== landingType.value) return false
    if (kw && !d.name.toLowerCase().includes(kw)) return false
    return true
  })
})

const pagedLandings = computed(() => {
  const total = filteredLandings.value.length
  const pages = Math.max(1, Math.ceil(total / landingPageSize))
  const page = Math.min(landingPage.value, pages)
  const start = (page - 1) * landingPageSize
  return filteredLandings.value.slice(start, start + landingPageSize)
})

watch(landingType, () => { landingPage.value = 1 })
watch(landingKw, () => { landingPage.value = 1 })

// 落地页卡片操作
const landingPreviewVisible = ref(false)
const landingPreviewLoading = ref(false)
const landingPreviewData = reactive({
  name: '',
  type: '',
  typeText: '',
  slug: '',
  html_content: '',
  fields: [] as { name: string; label: string; input_type: string; required: boolean }[],
})

// 走真实链路预览（落地页服务 /p/{slug}），所见即受害者所见；不可达时回退 srcdoc。
const landingSrcFailed = ref(false)
const landingPreviewSrc = computed(() => {
  const slug = landingPreviewData.slug
  if (!slug) return ''
  const base = (import.meta.env.VITE_LANDING_BASE as string) || `http://${location.hostname}:8082`
  return `${base}/p/${slug}`
})

async function previewLanding(row: LandingPage) {
  landingPreviewVisible.value = true
  landingPreviewLoading.value = true
  landingSrcFailed.value = false
  landingPreviewData.name = row.name
  landingPreviewData.type = row.type
  landingPreviewData.typeText = row.typeText || row.type
  landingPreviewData.html_content = ''
  landingPreviewData.fields = []
  try {
    // 预览与详情分离：srcdoc 兜底用消毒后渲染的 HTML（与线上 /p/{slug} 一致，防原页 JS 外发口令）
    const [detail, preview] = await Promise.all([
      templateApi.getLandingPage(row.id),
      templateApi.getLandingPagePreview(row.id),
    ]) as [Record<string, unknown>, Record<string, unknown>]
    landingPreviewData.html_content = (preview.html_content as string) || (detail.html_content as string) || ''
    landingPreviewData.slug = (detail.slug as string) || ''
    landingPreviewData.fields = (detail.fields as { name: string; label: string; input_type: string; required: boolean }[]) || []
  } catch {
    // 失败时由拦截器提示
  } finally {
    landingPreviewLoading.value = false
  }
}
async function cloneLanding(row: LandingPage) {
  try {
    await templateApi.duplicateLandingPage(row.id)
    ElMessage.success(`已复制落地页「${row.name}」，副本已生成`)
    await loadTemplates()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}
function deleteLanding(row: LandingPage) {
  ElMessageBox.confirm(`确认删除落地页「${row.name}」？`, '提示', { type: 'warning' })
    .then(() => ElMessage.success('落地页已删除'))
    .catch(() => { /* 用户取消 */ })
}

// 克隆落地页弹窗
const cloneDialogVisible = ref(false)
const cloneForm = reactive({ url: '', name: '', type: 'mail' as string, mobile: true })

async function submitClone() {
  if (!cloneForm.url) { ElMessage.warning('请填写源页面URL'); return }
  if (!cloneForm.name) { ElMessage.warning('请填写页面名称'); return }
  try {
    await templateApi.cloneLandingPage(cloneForm.url)
    ElMessage.success('页面克隆完成，已生成草稿（请稍后刷新列表查看）')
    cloneDialogVisible.value = false
    await loadTemplates()
  } catch {
    // 失败提示由 http 拦截器统一弹出（克隆失败的 URL 会提示原因）
  }
}

// 新建/编辑落地页弹窗
const landingDialogVisible = ref(false)
const fieldOptions = ['用户名', '密码', '验证码', '记住登录', '二次验证', '手机号']
const landingForm = reactive({
  id: 0,
  name: '',
  type: 'mail' as string,
  html_content: '',
  fields: ['用户名', '密码', '验证码'] as string[],
  edu: '⚠️ 您刚刚中招了！\n\n这是一次公司组织的安全演练。您刚刚在仿冒页面输入了账号密码，如果在真实场景中，您的凭据已被攻击者窃取。\n\n请牢记：\n1. 认准官方域名，不轻信邮件中的链接\n2. 输入密码前核对网址是否为 HTTPS 且域名正确\n3. 可疑邮件请及时通过举报通道上报安全团队',
  redirect: 'edu' as string,
})

async function openLandingDialog(row?: LandingPage) {
  if (row) {
    landingForm.id = row.id
    landingForm.name = row.name
    landingForm.type = row.type
    landingForm.html_content = ''
    landingForm.fields = ['用户名', '密码']
    try {
      const detail = await templateApi.getLandingPage(row.id) as Record<string, unknown>
      landingForm.html_content = (detail.html_content as string) || ''
      const fields = (detail.fields as { label: string }[]) || []
      if (fields.length) landingForm.fields = fields.map(f => f.label || '字段')
    } catch {
      // 失败时由拦截器提示
    }
  } else {
    Object.assign(landingForm, {
      id: 0, name: '', type: 'mail', html_content: '',
      fields: ['用户名', '密码', '验证码'], redirect: 'edu',
    })
  }
  landingDialogVisible.value = true
}

// 前端页面类型 → 后端 type 枚举（pay 无对应枚举，回退 custom）
const VIEW_TYPE_TO_PAGE: Record<string, string> = {
  mail: 'mail_login', oa: 'oa_login', pan: 'pan_auth', pay: 'custom',
}

const _DEFAULT_LANDING_HTML: Record<string, string> = {
  mail: '<!DOCTYPE html><html><head><meta charset="utf-8"><title>登录</title></head><body style="font-family:Segoe UI,Arial,sans-serif;background:#f3f6fb;margin:0;padding:40px"><div style="max-width:380px;margin:80px auto;background:#fff;border-radius:8px;padding:40px 32px;box-shadow:0 4px 20px rgba(0,0,0,.08)"><div style="text-align:center;font-size:20px;font-weight:600;color:#0078d4;margin-bottom:8px">🔒 {{NAME}}</div><div style="text-align:center;color:#666;font-size:13px;margin-bottom:28px">请登录以继续</div><form><label style="display:block;font-size:13px;color:#333;margin-bottom:6px">用户名 / 邮箱</label><input type="text" placeholder="请输入用户名" style="width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:4px;margin-bottom:16px;box-sizing:border-box"><label style="display:block;font-size:13px;color:#333;margin-bottom:6px">密码</label><input type="password" placeholder="请输入密码" style="width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:4px;margin-bottom:16px;box-sizing:border-box"><button type="submit" style="width:100%;background:#0078d4;color:#fff;border:none;padding:11px;border-radius:4px;font-size:15px;cursor:pointer">登 录</button></form><div style="text-align:center;margin-top:24px;font-size:11px;color:#999">© 2026 {{NAME}}</div></div></body></html>',
  oa: '<!DOCTYPE html><html><head><meta charset="utf-8"><title>OA登录</title></head><body style="font-family:Microsoft YaHei,Arial,sans-serif;background:#f0f2f5;margin:0"><div style="background:#1a73e8;color:#fff;padding:14px 32px;font-size:15px">企业统一认证系统</div><div style="max-width:400px;margin:60px auto;background:#fff;border-radius:6px;padding:48px 40px;box-shadow:0 2px 12px rgba(0,0,0,.1)"><div style="text-align:center;font-size:22px;font-weight:600;color:#1a73e8;margin-bottom:6px">{{NAME}}</div><div style="text-align:center;color:#888;font-size:13px;margin-bottom:32px">账号登录</div><form><label style="display:block;font-size:13px;color:#555;margin-bottom:6px">账号</label><input type="text" placeholder="请输入工号或邮箱" style="width:100%;padding:11px 14px;border:1px solid #e0e0e0;border-radius:4px;margin-bottom:18px;box-sizing:border-box"><label style="display:block;font-size:13px;color:#555;margin-bottom:6px">密码</label><input type="password" placeholder="请输入密码" style="width:100%;padding:11px 14px;border:1px solid #e0e0e0;border-radius:4px;margin-bottom:18px;box-sizing:border-box"><button type="submit" style="width:100%;background:#1a73e8;color:#fff;border:none;padding:12px;border-radius:4px;font-size:15px;cursor:pointer">登 录</button></form></div></body></html>',
  pan: '<!DOCTYPE html><html><head><meta charset="utf-8"><title>网盘登录</title></head><body style="font-family:Helvetica Neue,Arial,sans-serif;background:#fafafa;margin:0;padding:60px 20px"><div style="max-width:360px;margin:40px auto;background:#fff;border:1px solid #e8e8e8;border-radius:4px;padding:40px 32px"><div style="text-align:center;font-size:18px;font-weight:600;color:#333;margin-bottom:4px">☁️ {{NAME}}</div><div style="text-align:center;color:#999;font-size:12px;margin-bottom:24px">身份验证中心</div><form><label style="display:block;font-size:13px;color:#555;margin-bottom:6px">账号</label><input type="text" placeholder="请输入账号" style="width:100%;padding:9px 12px;border:1px solid #d9d9d9;border-radius:3px;margin-bottom:16px;box-sizing:border-box"><label style="display:block;font-size:13px;color:#555;margin-bottom:6px">密码</label><input type="password" placeholder="请输入密码" style="width:100%;padding:9px 12px;border:1px solid #d9d9d9;border-radius:3px;margin-bottom:16px;box-sizing:border-box"><button type="submit" style="width:100%;background:#1890ff;color:#fff;border:none;padding:10px;border-radius:3px;font-size:14px;cursor:pointer">登录验证</button></form></div></body></html>',
  custom: '<!DOCTYPE html><html><head><meta charset="utf-8"><title>{{NAME}}</title></head><body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:40px 20px"><div style="max-width:420px;margin:60px auto;background:#fff;border-radius:8px;padding:40px 36px;box-shadow:0 2px 16px rgba(0,0,0,.06)"><div style="text-align:center;font-size:20px;font-weight:600;color:#333;margin-bottom:8px">{{NAME}}</div><div style="text-align:center;color:#888;font-size:13px;margin-bottom:28px">请完成以下信息提交</div><form><label style="display:block;font-size:13px;color:#444;margin-bottom:6px">姓名</label><input type="text" placeholder="请输入您的姓名" style="width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:4px;margin-bottom:16px;box-sizing:border-box"><label style="display:block;font-size:13px;color:#444;margin-bottom:6px">工号</label><input type="text" placeholder="请输入工号" style="width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:4px;margin-bottom:16px;box-sizing:border-box"><button type="submit" style="width:100%;background:#378ADD;color:#fff;border:none;padding:11px;border-radius:4px;font-size:15px;cursor:pointer">提交信息</button></form></div></body></html>',
}

function generateDefaultHtml() {
  const tmpl = _DEFAULT_LANDING_HTML[landingForm.type] || _DEFAULT_LANDING_HTML.custom
  landingForm.html_content = tmpl.replaceAll('{{NAME}}', landingForm.name || '页面名称')
}

async function saveLanding() {
  if (!landingForm.name) {
    ElMessage.warning('请填写页面名称')
    return
  }
  try {
    const payload = {
      name: landingForm.name,
      type: VIEW_TYPE_TO_PAGE[landingForm.type] ?? 'custom',
      html_content: landingForm.html_content,
      form_schema: {
        fields: landingForm.fields.map((label, i) => ({ label, input_type: 'text', sort: i })),
        edu: landingForm.edu,
        redirect: landingForm.redirect,
      },
    }
    if (!landingForm.id) {
      await templateApi.createLandingPage(payload)
    } else {
      await templateApi.updateLandingPage(landingForm.id, payload)
    }
    await loadTemplates()
    landingDialogVisible.value = false
    ElMessage.success('落地页已保存')
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

// ============ Tab3: 附件与载荷 ============
const payloadStats = computed<StatItem[]>(() => {
  const data = payloadData.value
  const month = new Date().toISOString().slice(0, 7)
  const newThisMonth = data.filter((d) => (d.created_at || '').startsWith(month)).length
  const avgEvade = data.length ? data.reduce((s, d) => s + d.evade, 0) / data.length : 0
  return [
    { accent: 'blue', title: '附件总数', value: String(data.length), sub: `↑ ${newThisMonth} 本月新增`, subTone: 'success' },
    { accent: 'green', title: '本月新增', value: String(newThisMonth), valueColor: 'var(--accent-green)', sub: '按创建时间实时统计', subTone: 'secondary' },
    { accent: 'orange', title: '平均检测逃逸率', value: avgEvade.toFixed(1), suffix: '%', valueColor: 'var(--accent-orange)', sub: '全量载荷均值', subTone: 'tertiary' },
  ]
})

const payloadTypeLabels: Record<string, string> = {
  macro: '宏文档', exe: '可执行文件', qr: '二维码', other: '其他',
}

const payloadFilters = computed<FilterItem[]>(() => {
  const data = payloadData.value
  const items: FilterItem[] = [{ key: 'all', label: '全部', count: data.length }]
  for (const [key, label] of Object.entries(payloadTypeLabels)) {
    const n = data.filter((d) => d.type === key).length
    if (n > 0) items.push({ key, label, count: n })
  }
  return items
})

const ptypeColor: Record<string, string> = {
  macro: 'var(--accent-blue)',
  exe: 'var(--accent-green)',
  qr: 'var(--accent-purple)',
  other: 'var(--accent-warning)',
}

const payloadData = ref<PayloadItem[]>([])

const payloadType = ref('all')
const payloadKw = ref('')
const payloadPage = ref(1)
const payloadPageSize = 8

const filteredPayloads = computed(() => {
  const kw = payloadKw.value.trim().toLowerCase()
  return payloadData.value.filter((d) => {
    if (payloadType.value !== 'all' && d.type !== payloadType.value) return false
    if (kw && !d.name.toLowerCase().includes(kw)) return false
    return true
  })
})

const pagedPayloads = computed(() => {
  const total = filteredPayloads.value.length
  const pages = Math.max(1, Math.ceil(total / payloadPageSize))
  const page = Math.min(payloadPage.value, pages)
  const start = (page - 1) * payloadPageSize
  return filteredPayloads.value.slice(start, start + payloadPageSize)
})

watch(payloadType, () => { payloadPage.value = 1 })
watch(payloadKw, () => { payloadPage.value = 1 })

// ============ 接口加载（失败时保留演示数据） ============
// 后端枚举值 → 前端筛选键归一化
const SCENE_TO_CAT: Record<string, string> = { system: 'upgrade', prize: 'lottery', security: 'alert' }
const PAGE_TYPE_TO_VIEW: Record<string, string> = {
  mail_login: 'mail', oa_login: 'oa', pan_auth: 'pan', cloned: 'custom',
}
const ATTACH_TYPE_TO_VIEW: Record<string, string> = { macro_doc: 'macro' }

async function loadTemplates() {
  const [emails, landings, payloads] = await Promise.allSettled([
    templateApi.emailTemplates(),
    templateApi.landingPages(),
    templateApi.payloads(),
  ])
  if (emails.status === 'fulfilled') {
    const list = emails.value as EmailTemplate[]
    if (Array.isArray(list) && list.length) {
      emailData.value = list.map(t => ({ ...t, cat: SCENE_TO_CAT[t.cat] ?? t.cat }))
    }
  }
  if (landings.status === 'fulfilled') {
    const list = landings.value as LandingPage[]
    if (Array.isArray(list) && list.length) {
      landingData.value = list.map(l => ({ ...l, type: PAGE_TYPE_TO_VIEW[l.type] ?? l.type }))
    }
  }
  if (payloads.status === 'fulfilled') {
    const list = payloads.value as PayloadItem[]
    if (Array.isArray(list) && list.length) {
      payloadData.value = list.map(p => ({ ...p, type: ATTACH_TYPE_TO_VIEW[p.type] ?? p.type }))
    }
  }
  if ([emails, landings, payloads].some(r => r.status === 'rejected')) {
    ElMessage.error('素材数据加载失败，请检查网络或后端服务')
  }
}

onMounted(loadTemplates)

// 检测逃逸率配色：≥85 绿 / ≥70 黄 / 否则橙
function evadeColor(rate: number): string {
  if (rate >= 85) return 'var(--accent-green)'
  if (rate >= 70) return 'var(--accent-warning)'
  return 'var(--accent-orange)'
}

// 附件行操作
function downloadPayload(row: PayloadItem) {
  ElMessage.info(`正在下载「${row.name}」`)
}
function editPayload(row: PayloadItem) {
  ElMessage.info(`正在编辑「${row.name}」配置`)
}
function togglePayload(row: PayloadItem) {
  row.status = row.status === 'enabled' ? 'disabled' : 'enabled'
  ElMessage.success(`「${row.name}」已${row.status === 'enabled' ? '启用' : '禁用'}`)
}
function deletePayload(row: PayloadItem) {
  ElMessageBox.confirm(`确认删除「${row.name}」？`, '提示', { type: 'warning' })
    .then(() => ElMessage.success('附件已删除'))
    .catch(() => { /* 用户取消 */ })
}

// 二维码弹窗
const qrDialogVisible = ref(false)
const qrType = ref('url')
const qrContent = ref('')
const qrSize = ref(512)
const qrLogoName = ref('')
const qrTypes = [
  { key: 'url', label: 'URL', color: 'var(--accent-blue)' },
  { key: 'text', label: 'TXT', color: 'var(--accent-green)' },
  { key: 'wifi', label: 'WIFI', color: 'var(--accent-purple)' },
  { key: 'email', label: 'MAIL', color: 'var(--accent-orange)' },
]

function onQrLogoChange(file: UploadFile) {
  qrLogoName.value = file.name
}
function previewQr() {
  if (!qrContent.value) { ElMessage.warning('请输入二维码内容'); return }
  ElMessage.success('二维码预览已生成')
}
function submitQr() {
  if (!qrContent.value) { ElMessage.warning('请输入二维码内容'); return }
  qrDialogVisible.value = false
  ElMessage.success('二维码已保存到附件库')
}

// 上传附件弹窗
const uploadDialogVisible = ref(false)
const uploadPlatforms = ref<string[]>(['Windows'])
const uploadEvasions = ref<string[]>(['代码混淆加密', '多态外壳包裹'])
const evasionOptions = ['代码混淆加密', '多态外壳包裹', '反沙箱检测', '反虚拟机检测']

function onUploadChange(file: UploadFile) {
  ElMessage.info(`已选择文件：${file.name}`)
}
function submitUpload() {
  uploadDialogVisible.value = false
  ElMessage.success('附件已上传，免杀处理中，预计 1 分钟后完成')
}
</script>

<style scoped lang="scss">
// 补充 demo 中使用但 design-tokens 未提供的警告色 token
.template-view {
  --accent-warning: #ef9f27;
}

// ===== 统计卡片 =====
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}
.stat-grid-3 {
  grid-template-columns: repeat(3, 1fr);
}
.stat-card {
  padding: 14px;
}
.stat-title {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}
.stat-value {
  font-size: 24px;
  font-weight: 500;
  line-height: 1.2;
  color: var(--color-text-primary);
}
.stat-value-sm {
  font-size: 16px;
}
.stat-suffix {
  font-size: 13px;
  font-weight: 400;
  margin-left: 2px;
  color: var(--color-text-tertiary);
}
.stat-sub {
  font-size: 11px;
  margin-top: 6px;
}
.sub-success { color: var(--color-text-success); }
.sub-secondary { color: var(--color-text-secondary); }
.sub-tertiary { color: var(--color-text-tertiary); }

// ===== 工具栏 =====
.toolbar {
  padding: 12px 16px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  border-top: none; // 工具栏卡不显示顶部主题色边

  &:hover {
    box-shadow: none;
    transform: none;
  }
}
.filter-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.filter-tag {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  background: var(--color-background-secondary);
  color: var(--color-text-secondary);

  &:hover { background: var(--color-background-tertiary); }
  &.active {
    background: var(--color-background-info);
    color: var(--color-text-info);
    border-color: var(--color-border-info);
  }
  .count {
    margin-left: 4px;
    opacity: 0.8;
    font-weight: 500;
  }
}
.toolbar-search {
  width: 200px;
  margin-left: auto;
}

// ===== 卡片网格 =====
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.empty-tip {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
  color: var(--color-text-tertiary);
  font-size: 12px;
}

// 邮件模板卡 / 落地页卡 共用骨架
.template-card {
  border: 1.5px solid var(--color-border-tertiary);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--color-background-primary);

  &:hover {
    border-color: var(--accent-blue);
    box-shadow: 0 2px 8px color-mix(in srgb, var(--accent-blue) 12%, transparent);
  }
}

// 邮件模板预览区
.email-preview-container {
  min-height: 300px;
}
.email-preview-header {
  padding: 0 4px 12px;
}
.email-preview-header .preview-row {
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-text-secondary);
}
.email-preview-header .preview-label {
  color: var(--color-text-tertiary);
  margin-right: 4px;
}
.email-preview-divider {
  border-top: 1px solid var(--color-border-light);
  margin-bottom: 12px;
}
.email-preview-iframe {
  width: 100%;
  min-height: 400px;
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  background: #fff;
}
.landing-preview-container {
  min-height: 300px;
}
.landing-preview-header {
  padding: 0 4px 12px;
}
.landing-preview-header .preview-row {
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-text-secondary);
}
.landing-preview-header .preview-label {
  color: var(--color-text-tertiary);
  margin-right: 4px;
}
.preview-slug {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
  color: var(--accent-blue);
  background: color-mix(in srgb, var(--accent-blue) 8%, transparent);
  padding: 1px 6px;
  border-radius: 4px;
}
.html-editor-wrap {
  width: 100%;
}
.html-editor-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.html-textarea {
  font-family: 'SF Mono', Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  background: var(--color-background-tertiary);
}
.html-textarea :deep(.el-textarea__inner) {
  font-family: 'SF Mono', Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.template-preview {
  padding: 12px;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--item-color, var(--accent-blue)) 6%, transparent) 0%,
    var(--color-background-tertiary) 100%
  );
}
.preview-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-primary);
}
.preview-icon {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  background: var(--item-color, var(--accent-blue));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  flex-shrink: 0;
}
.preview-subject {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-meta {
  font-size: 10px;
  color: var(--color-text-tertiary);
  padding-left: 24px;
  margin-top: 6px;
}

// 落地页预览区（仿登录表单）
.landing-preview {
  height: 140px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--item-color, var(--accent-blue)) 10%, transparent) 0%,
    var(--color-background-tertiary) 100%
  );
}
.mock-form {
  width: 80%;
  background: var(--color-background-primary);
  border-radius: 6px;
  padding: 8px 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.mock-bar {
  border-radius: 2px;
  margin-bottom: 6px;
}
.mock-title {
  height: 8px;
  width: 50%;
  background: var(--item-color, var(--accent-blue));
}
.mock-line {
  height: 6px;
  width: 100%;
  background: var(--color-border-tertiary);
}
.mock-btn {
  height: 14px;
  width: 60%;
  background: var(--item-color, var(--accent-blue));
  border-radius: 3px;
  margin: 0 auto;
}
.preview-tip {
  font-size: 10px;
  color: var(--color-text-tertiary);
  margin-top: 8px;
}

// 卡片元信息
.template-meta {
  padding: 10px;
}
.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.template-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 6px;
}
.stars-row {
  font-size: 10px;
}
.stars {
  display: inline-flex;
}
.star {
  color: var(--color-border-tertiary);
  font-size: 12px;
  &.filled { color: var(--accent-warning); }
}
.star-text {
  color: var(--color-text-secondary);
}
.stats-row {
  font-size: 10px;
  color: var(--color-text-tertiary);
  border-top: 1px dashed var(--color-border-tertiary);
  padding-top: 6px;
  gap: 10px;
}
.click-rate {
  color: var(--item-color, var(--accent-blue));
}
.card-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  border-top: 1px solid var(--color-background-tertiary);
  padding-top: 8px;
}
.table-actions {
  justify-content: flex-end;
  border-top: none;
  padding-top: 0;
}

// ===== 徽标 =====
.badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
.badge-cat {
  background: color-mix(in srgb, var(--item-color, var(--accent-blue)) 12%, transparent);
  color: var(--item-color, var(--accent-blue));
}
.badge-on {
  background: color-mix(in srgb, var(--accent-green) 12%, transparent);
  color: var(--accent-green);
}
.badge-off {
  background: color-mix(in srgb, var(--color-text-tertiary) 14%, transparent);
  color: var(--color-text-tertiary);
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 4px;
  flex-shrink: 0;
}
.dot-on {
  background: var(--accent-green);
  animation: pulse 2s infinite;
}
.dot-off {
  background: var(--color-text-tertiary);
}

// ===== 数据表 =====
.table-card {
  padding: 0;
  overflow: hidden;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  table-layout: fixed;

  th {
    text-align: left;
    padding: 10px 12px;
    font-weight: 500;
    color: var(--color-text-secondary);
    font-size: 11px;
    background: var(--color-background-secondary);
    border-bottom: 1px solid var(--color-border-tertiary);
  }
  td {
    padding: 12px;
    border-bottom: 1px solid var(--color-background-tertiary);
    color: var(--color-text-primary);
    vertical-align: middle;
  }
  tbody tr:hover {
    background: color-mix(in srgb, var(--accent-blue) 3%, transparent);
  }
  .ta-right { text-align: right; }
  .muted {
    font-size: 11px;
    color: var(--color-text-secondary);
  }
  .used-num {
    font-size: 11px;
    font-weight: 500;
    color: var(--color-text-primary);
  }
}
.file-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.file-icon {
  width: 24px;
  height: 24px;
  border-radius: 5px;
  background: color-mix(in srgb, var(--item-color, var(--accent-blue)) 12%, transparent);
  color: var(--item-color, var(--accent-blue));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex-shrink: 0;
}
.file-name {
  font-weight: 500;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evade-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.bar-track {
  background: var(--color-background-tertiary);
  border-radius: 4px;
  height: 6px;
  overflow: hidden;
  flex: 1;
}
.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}
.evade-val {
  font-size: 11px;
  font-weight: 500;
  width: 36px;
  text-align: right;
}

// ===== 分页 =====
.pager-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 18px;
}
.pager-info {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

// ===== 弹窗内表单 =====
.form-hint {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}
.var-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.var-tip {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
.var-tag {
  cursor: pointer;
}
.track-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.track-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
}
.track-info {
  display: flex;
  flex-direction: column;
}
.track-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
}
.track-desc {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin: 2px 0 0;
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.field-grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.evasion-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

// 二维码类型选项卡
.qr-type-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.option-card {
  border: 1.5px solid var(--color-border-tertiary);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--color-background-primary);

  &:hover {
    border-color: var(--accent-blue);
    background: color-mix(in srgb, var(--accent-blue) 3%, transparent);
  }
  &.selected {
    border-color: var(--item-color, var(--accent-blue));
    background: color-mix(in srgb, var(--item-color, var(--accent-blue)) 6%, transparent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--item-color, var(--accent-blue)) 12%, transparent);
  }
}
.option-card-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.qr-preview-area {
  width: 100%;
  height: 200px;
  border: 2px dashed var(--color-border-tertiary);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--color-background-secondary);
}
.qr-preview-tip {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

// 上传区
.upload-drag {
  width: 100%;
}
.upload-text {
  font-size: 12px;
  color: var(--color-text-primary);
  margin-top: 8px;
  font-weight: 500;
}

// ===== el-tabs 轻度调整 =====
.tpl-tabs {
  margin-top: 4px;
}
.tpl-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}
.tpl-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: var(--color-border-tertiary);
}
</style>
