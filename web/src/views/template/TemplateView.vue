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
          <el-button type="success" size="small" :icon="MagicStick" @click="aiGenVisible = true">AI生成</el-button>
        </div>

        <!-- AI 生成草稿（审核通过后自动入库） -->
        <div class="card ai-draft-strip" v-if="emailDrafts.length">
          <div class="card-title">
            ✨ AI 生成草稿
            <span class="ai-draft-hint">审核通过后自动成为模板，无需复制粘贴</span>
          </div>
          <AiDraftCard v-for="d in emailDrafts" :key="d.id" :draft="d"
            @preview="previewAiDraft" @approve="approveAiDraft" @discard="discardAiDraft" />
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
          <el-button type="success" size="small" :icon="MagicStick" @click="aiLandingVisible = true">AI生成</el-button>
        </div>

        <!-- AI 生成草稿（审核通过后自动入库） -->
        <div class="card ai-draft-strip" v-if="landingDrafts.length">
          <div class="card-title">
            ✨ AI 生成草稿
            <span class="ai-draft-hint">审核通过后自动成为落地页，无需复制粘贴</span>
          </div>
          <AiDraftCard v-for="d in landingDrafts" :key="d.id" :draft="d"
            @preview="previewAiDraft" @approve="approveAiDraft" @discard="discardAiDraft" />
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
                <el-button size="small" link @click="cloneLanding(l)">复制</el-button>
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
          <el-button size="small" :icon="Iphone" disabled>生成二维码</el-button>
          <el-button type="primary" size="small" :icon="Upload" @click="openUploadDialog()">上传附件</el-button>
          <el-button type="success" size="small" :icon="MagicStick" @click="aiPayloadVisible = true">AI生成</el-button>
          <el-tag size="small" type="info" effect="plain">支持 docx/xlsx/pdf/zip 文档附件，宏/EXE 载荷未开放</el-tag>
        </div>

        <!-- AI 生成草稿（审核通过后渲染真实文件入库） -->
        <div class="card ai-draft-strip" v-if="payloadDrafts.length">
          <div class="card-title">
            ✨ AI 生成草稿
            <span class="ai-draft-hint">审核通过后渲染为 docx/xlsx 文件写入附件库（投递自动注入运行追踪）</span>
          </div>
          <AiDraftCard v-for="d in payloadDrafts" :key="d.id" :draft="d"
            @preview="previewAiDraft" @approve="approveAiDraft" @discard="discardAiDraft" />
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

      <el-tab-pane label="企微消息模板" name="wecom">
        <div class="toolbar" style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
          <el-button type="primary" @click="openWecomTplDialog()">+ 新建消息模板</el-button>
          <el-button type="success" :icon="MagicStick" @click="aiWecomVisible = true">AI生成</el-button>
          <span class="muted" style="font-size:12px;">企微演练（社交媒体）投递的 textcard 卡片素材；需审核通过后才能被演练选用</span>
        </div>

        <!-- AI 生成草稿（审核通过后自动入库） -->
        <div class="card ai-draft-strip" v-if="wecomDrafts.length">
          <div class="card-title">
            ✨ AI 生成草稿
            <span class="ai-draft-hint">审核通过后自动成为企微消息模板</span>
          </div>
          <AiDraftCard v-for="d in wecomDrafts" :key="d.id" :draft="d"
            @preview="previewAiDraft" @approve="approveAiDraft" @discard="discardAiDraft" />
        </div>

        <el-table :data="wecomTplRows" size="small" v-loading="wecomTplLoading">
          <el-table-column prop="name" label="模板名称" min-width="140" />
          <el-table-column prop="title" label="卡片标题" min-width="160" show-overflow-tooltip />
          <el-table-column prop="description" label="卡片摘要" min-width="200" show-overflow-tooltip />
          <el-table-column label="按钮/链接" width="150">
            <template #default="{ row }">
              <div style="font-size:12px;">{{ row.btn_text }}</div>
              <div class="muted" style="font-size:11px;">{{ row.url_mode === 'track' ? '追踪短链' : '自定义URL' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <span class="badge" :class="row.status === 'approved' ? 'badge-on' : row.status === 'discarded' ? 'badge-off' : 'badge-cat'">
                {{ (WECOM_STATUS_TEXT as Record<string, string>)[row.status] ?? row.status }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="used_count" label="引用" width="70" align="center" />
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <div class="card-actions table-actions">
                <el-button size="small" link @click="openWecomTplDialog(row)">编辑</el-button>
                <el-button v-if="row.status !== 'approved'" size="small" link type="success" @click="reviewWecomTpl(row, 'approved')">通过</el-button>
                <el-button v-if="row.status !== 'discarded'" size="small" link type="warning" @click="reviewWecomTpl(row, 'discarded')">驳回</el-button>
                <el-button size="small" link type="danger" @click="deleteWecomTpl(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- 新建/编辑企微消息模板弹窗 -->
        <el-dialog v-model="wecomTplDialogVisible" :title="wecomTplForm.id ? '编辑企微消息模板' : '新建企微消息模板'" width="640px" destroy-on-close>
          <el-form :model="wecomTplForm" label-width="100px">
            <el-form-item label="模板名称" required>
              <el-input v-model="wecomTplForm.name" placeholder="如：IT安全中心密码到期提醒" />
            </el-form-item>
            <el-form-item label="消息类型">
              <el-select v-model="wecomTplForm.msg_type" style="width: 100%">
                <el-option label="卡片消息（textcard）" value="textcard" />
                <el-option label="文本消息（预留）" value="text" disabled />
              </el-select>
            </el-form-item>
            <el-form-item label="卡片标题" required>
              <el-input v-model="wecomTplForm.title" maxlength="128" show-word-limit placeholder="支持变量 {{.FirstName}} {{.Department}} {{.Date}}" />
            </el-form-item>
            <el-form-item label="卡片摘要" required>
              <el-input v-model="wecomTplForm.description" type="textarea" :rows="3" maxlength="512" show-word-limit placeholder="支持变量 {{.FirstName}} {{.Department}} {{.ResetURL}}" />
            </el-form-item>
            <el-form-item label="按钮文案">
              <el-input v-model="wecomTplForm.btn_text" maxlength="16" placeholder="查看详情" />
            </el-form-item>
            <el-form-item label="链接模式">
              <el-radio-group v-model="wecomTplForm.url_mode">
                <el-radio value="track">追踪短链（点击统计 + 跳转落地页，推荐）</el-radio>
                <el-radio value="custom">自定义 URL</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="wecomTplForm.url_mode === 'custom'" label="自定义URL">
              <el-input v-model="wecomTplForm.custom_url" placeholder="https://…（须落在独立演练域，红线3）" />
            </el-form-item>
            <div class="form-hint" style="font-size:11px;color:var(--color-text-tertiary);margin-left:100px;">文案禁用「微信安全中心/官方通知」等冒充官方字样（合规红线），请以内部部门名义（IT 部/HR）；审核状态经列表「通过/驳回」流转</div>
          </el-form>
          <template #footer>
            <el-button @click="wecomTplDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="wecomTplSaving" @click="saveWecomTpl">保存</el-button>
          </template>
        </el-dialog>
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
              <div class="form-hint">演练发起时若选择了伪装发件人，发件身份以其配置为准，此处仅作默认值</div>
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

    <!-- ====== 弹窗：AI 生成邮件模板 ====== -->
    <el-dialog v-model="aiGenVisible" title="AI 生成邮件模板" width="480px">
      <el-form label-width="90px" size="small">
        <el-form-item label="场景">
          <el-select v-model="aiGenForm.scene" filterable allow-create default-first-option style="width: 100%">
            <el-option label="财务报销" value="finance" />
            <el-option label="HR通知" value="hr" />
            <el-option label="系统升级" value="system" />
            <el-option label="中奖通知" value="lottery" />
            <el-option label="节假日问候" value="holiday" />
            <el-option label="安全告警" value="security" />
            <el-option label="其他" value="other" />
          </el-select>
          <div class="form-hint">可直接输入自定义场景，如「供应商对账」「年终奖发放」</div>
        </el-form-item>
        <el-form-item label="目标人群">
          <el-input v-model="aiGenForm.audience" placeholder="例如：全体员工 / 财务部" />
        </el-form-item>
        <el-form-item label="语气">
          <el-select v-model="aiGenForm.tone" style="width: 100%">
            <el-option label="正式" value="正式" />
            <el-option label="轻松" value="轻松" />
            <el-option label="紧迫" value="紧迫" />
          </el-select>
        </el-form-item>
        <el-form-item label="识别难度">
          <el-slider v-model="aiGenForm.difficulty" :min="1" :max="5" show-stops
            :marks="{ 1: '易', 3: '中', 5: '难' }" />
        </el-form-item>
      </el-form>
      <div class="form-hint">生成结果先进入草稿审核，确认入库后自动出现在模板列表中（AI 产出草稿制为硬约束）。</div>
      <template #footer>
        <el-button @click="aiGenVisible = false">取消</el-button>
        <el-button type="primary" :loading="aiGenerating" @click="submitAiGen">生成草稿</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：AI 生成落地页 ====== -->
    <el-dialog v-model="aiLandingVisible" title="AI 生成落地页" width="480px">
      <el-form label-width="90px" size="small">
        <el-form-item label="页面类型">
          <el-select v-model="aiLandingForm.scene" style="width: 100%">
            <el-option label="邮箱登录" value="mail" />
            <el-option label="OA系统" value="oa" />
            <el-option label="网盘认证" value="pan" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="企业名称">
          <el-input v-model="aiLandingForm.company" placeholder="用于页面标题/LOGO，如：某某科技" />
        </el-form-item>
        <el-form-item label="目标人群">
          <el-input v-model="aiLandingForm.audience" placeholder="例如：全体员工 / 财务部" />
        </el-form-item>
        <el-form-item label="语气">
          <el-select v-model="aiLandingForm.tone" style="width: 100%">
            <el-option label="正式" value="正式" />
            <el-option label="轻松" value="轻松" />
            <el-option label="紧迫" value="紧迫" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="form-hint">生成结果先进入草稿审核，确认入库后自动出现在落地页列表中（AI 产出草稿制为硬约束）。</div>
      <template #footer>
        <el-button @click="aiLandingVisible = false">取消</el-button>
        <el-button type="primary" :loading="aiLandingGenerating" @click="submitAiLanding">生成草稿</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：AI 生成企微消息模板 ====== -->
    <el-dialog v-model="aiWecomVisible" title="AI 生成企微消息模板" width="480px">
      <el-form label-width="90px" size="small">
        <el-form-item label="场景">
          <el-select v-model="aiWecomForm.scene" filterable allow-create default-first-option style="width: 100%">
            <el-option label="系统升级" value="system" />
            <el-option label="HR通知" value="hr" />
            <el-option label="财务报销" value="finance" />
            <el-option label="中奖通知" value="lottery" />
            <el-option label="节假日问候" value="holiday" />
            <el-option label="安全告警" value="security" />
            <el-option label="其他" value="other" />
          </el-select>
          <div class="form-hint">可直接输入自定义场景，如「门禁系统升级」</div>
        </el-form-item>
        <el-form-item label="目标人群">
          <el-input v-model="aiWecomForm.audience" placeholder="例如：全体员工 / 财务部" />
        </el-form-item>
        <el-form-item label="语气">
          <el-select v-model="aiWecomForm.tone" style="width: 100%">
            <el-option label="正式" value="正式" />
            <el-option label="轻松" value="轻松" />
            <el-option label="紧迫" value="紧迫" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="form-hint">产出 textcard 卡片（标题+摘要+按钮），审核通过自动入库；文案以内部部门名义行文，禁用冒充官方字样（合规红线）。</div>
      <template #footer>
        <el-button @click="aiWecomVisible = false">取消</el-button>
        <el-button type="primary" :loading="aiWecomGenerating" @click="submitAiWecom">生成草稿</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：AI 生成诱饵文档 ====== -->
    <el-dialog v-model="aiPayloadVisible" title="AI 生成诱饵文档" width="480px">
      <el-form label-width="90px" size="small">
        <el-form-item label="文档场景">
          <el-select v-model="aiPayloadForm.scene" filterable allow-create default-first-option style="width: 100%">
            <el-option label="通知公告" value="通知" />
            <el-option label="工资明细" value="工资明细" />
            <el-option label="补贴通知" value="补贴通知" />
            <el-option label="会议邀请" value="会议邀请" />
            <el-option label="培训材料" value="培训材料" />
            <el-option label="其他" value="其他" />
          </el-select>
          <div class="form-hint">可直接输入自定义场景，如「办公软件续费通知」</div>
        </el-form-item>
        <el-form-item label="文档格式">
          <el-radio-group v-model="aiPayloadForm.doc_type">
            <el-radio value="docx">Word 文档（打开可追踪）</el-radio>
            <el-radio value="xlsx">Excel 明细（打开可追踪）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="目标人群">
          <el-input v-model="aiPayloadForm.audience" placeholder="例如：全体员工 / 财务部" />
        </el-form-item>
        <el-form-item label="语气">
          <el-select v-model="aiPayloadForm.tone" style="width: 100%">
            <el-option label="正式" value="正式" />
            <el-option label="轻松" value="轻松" />
            <el-option label="紧迫" value="紧迫" />
          </el-select>
        </el-form-item>
      </el-form>
      <!-- v-pre：提示含字面量模板变量 {{.FirstName}}，跳过 Vue 插值解析 -->
      <div v-pre class="form-hint">仅良性文档（docx/xlsx），宏/EXE 载荷未开放（红线 6）。确认入库时渲染真实文件写入附件库；投递时自动注入附件运行追踪 beacon 并做 {{.FirstName}} 等变量个性化。</div>
      <template #footer>
        <el-button @click="aiPayloadVisible = false">取消</el-button>
        <el-button type="primary" :loading="aiPayloadGenerating" @click="submitAiPayload">生成草稿</el-button>
      </template>
    </el-dialog>

    <!-- ====== 弹窗：AI 草稿预览（按类型渲染） ====== -->
    <el-dialog v-model="aiPreviewVisible" title="草稿预览" width="720px">
      <template v-if="aiPreview">
        <!-- 邮件模板 -->
        <template v-if="aiPreview.kind === 'email_template'">
          <el-descriptions :column="2" size="small" border style="margin-bottom: 12px">
            <el-descriptions-item label="主题">{{ aiPreview.subject }}</el-descriptions-item>
            <el-descriptions-item label="发件人">{{ aiPreview.sender }}</el-descriptions-item>
          </el-descriptions>
          <div class="tpl-preview-box" v-html="aiPreview.body"></div>
        </template>
        <!-- 落地页 -->
        <template v-else-if="aiPreview.kind === 'landing_page'">
          <el-descriptions :column="2" size="small" border style="margin-bottom: 12px">
            <el-descriptions-item label="页面名称">{{ aiPreview.name }}</el-descriptions-item>
            <el-descriptions-item label="表单字段">{{ aiPreview.fieldsText }}</el-descriptions-item>
          </el-descriptions>
          <iframe
            v-if="aiPreview.html_content"
            :srcdoc="aiPreview.html_content"
            class="email-preview-iframe"
            sandbox="allow-scripts"
          />
        </template>
        <!-- 企微卡片 -->
        <template v-else-if="aiPreview.kind === 'wecom_template'">
          <div class="wecom-preview-box">
            <div class="wecom-preview-title">{{ aiPreview.title }}</div>
            <div class="wecom-preview-desc">{{ aiPreview.description }}</div>
            <div class="wecom-preview-btn">{{ aiPreview.btn_text || '查看详情' }}</div>
          </div>
        </template>
        <!-- 诱饵文档 -->
        <template v-else-if="aiPreview.kind === 'attachment'">
          <div class="tpl-preview-box">
            <h2 style="text-align:center;font-size:18px;margin:0 0 16px">{{ aiPreview.title }}</h2>
            <p v-for="(p, i) in aiPreview.paragraphs" :key="i" style="line-height:1.8;margin:6px 0">{{ p }}</p>
            <table v-if="aiPreview.table" class="doc-preview-table">
              <thead>
                <tr><th v-for="(h, i) in aiPreview.table.headers" :key="i">{{ h }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="(r, i) in aiPreview.table.rows" :key="i">
                  <td v-for="(c, j) in r" :key="j">{{ c }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <el-empty v-else description="该类型草稿暂不支持预览" />
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
          <div class="preview-row" v-if="landingPreviewData.slug"><span class="preview-label">访问路径：</span><span class="preview-slug">{{ landingPreviewData.custom_path || `/p/${landingPreviewData.slug}` }}</span></div>
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
        <el-form-item label="自定义路径">
          <el-input v-model="landingForm.custom_path" placeholder="留空 = 默认 /p/{随机slug}；可设 / 或 /login.html（仿真防识别）" />
          <div class="form-hint">访问地址变为「追踪/落地域 + 自定义路径」，如 https://oa-verify.cn/login.html；/ 表示根路径。全局唯一，不能使用平台保留路径（/p/ /t/ /px/ /pa/）。</div>
        </el-form-item>
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
            ref="uploadRef"
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            :on-change="onUploadChange"
            :on-exceed="onUploadExceed"
            class="upload-drag"
          >
            <el-icon :size="32" color="var(--color-text-tertiary)"><UploadFilled /></el-icon>
            <div class="upload-text">点击或拖拽文件到此处上传</div>
            <template #tip>
              <div class="form-hint">支持 .docx .xlsx .pdf .zip 良性文档，单文件 ≤ 20MB；宏/EXE 载荷未开放</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUpload">上传附件</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'
import { Plus, Search, Upload, Link, UploadFilled, Iphone, Picture, MagicStick } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import AiDraftCard, { type AiDraft } from '@/components/ai/AiDraftCard.vue'
import { aiApi, attachmentApi, templateApi } from '@/api'

// ===== 类型定义 =====
type TabName = 'email' | 'landing' | 'payload' | 'wecom'
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
  source?: string
  typeText: string
  slug?: string
  custom_path?: string | null
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
async function testEmail(row: EmailTemplate) {
  let to: string
  try {
    const r = await ElMessageBox.prompt(
      '请输入白名单测试收件邮箱（真实发送，请使用本人/登记邮箱）',
      `测试发送「${row.name}」`,
      {
        inputPattern: /^[^@\s]+@[^@\s]+\.[^@\s]+$/,
        inputErrorMessage: '请输入有效邮箱地址',
      },
    )
    to = (r.value || '').trim()
  } catch { return /* 用户取消 */ }
  try {
    const res = await templateApi.testSendEmailTemplate(row.id, [to])
    if (res?.ok) ElMessage.success(res.message)
    else ElMessage.warning(res?.message || '测试发送失败')
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
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
async function deleteEmail(row: EmailTemplate) {
  try {
    await ElMessageBox.confirm(
      `确认删除模板「${row.name}」？被演练引用时将被拒绝。`,
      '删除模板', { type: 'warning' },
    )
  } catch { return /* 用户取消 */ }
  try {
    await templateApi.deleteEmailTemplate(row.id)
    ElMessage.success('模板已删除')
    await loadTemplates()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
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
  const cloned = data.filter((d) => d.source === 'cloned').length
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
  custom_path: '',
  html_content: '',
  fields: [] as { name: string; label: string; input_type: string; required: boolean }[],
})

// 走真实链路预览（落地页服务，自定义路径优先），所见即受害者所见；不可达时回退 srcdoc。
const landingSrcFailed = ref(false)
const landingPreviewSrc = computed(() => {
  if (!landingPreviewData.slug) return ''
  const base = (import.meta.env.VITE_LANDING_BASE as string) || `http://${location.hostname}:8082`
  const path = landingPreviewData.custom_path || `/p/${landingPreviewData.slug}`
  return `${base}${path}`
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
    landingPreviewData.custom_path = (detail.custom_path as string) || ''
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
async function deleteLanding(row: LandingPage) {
  try {
    await ElMessageBox.confirm(
      `确认删除落地页「${row.name}」？被演练引用时将被拒绝。`,
      '删除落地页', { type: 'warning' },
    )
  } catch { return /* 用户取消 */ }
  try {
    await templateApi.deleteLandingPage(row.id)
    ElMessage.success('落地页已删除')
    await loadTemplates()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

// 克隆落地页弹窗
const cloneDialogVisible = ref(false)
const cloneForm = reactive({ url: '', name: '', type: 'mail' as string, mobile: true })

async function submitClone() {
  if (!cloneForm.url) { ElMessage.warning('请填写源页面URL'); return }
  if (!cloneForm.name) { ElMessage.warning('请填写页面名称'); return }
  try {
    await templateApi.cloneLandingPage(
      cloneForm.url,
      cloneForm.name,
      VIEW_TYPE_TO_PAGE[cloneForm.type] ?? 'cloned',
    )
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
  custom_path: '',
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
    landingForm.custom_path = ''
    landingForm.fields = ['用户名', '密码']
    try {
      const detail = await templateApi.getLandingPage(row.id) as Record<string, unknown>
      landingForm.html_content = (detail.html_content as string) || ''
      landingForm.custom_path = (detail.custom_path as string) || ''
      const fields = (detail.fields as { label: string }[]) || []
      if (fields.length) landingForm.fields = fields.map(f => f.label || '字段')
    } catch {
      // 失败时由拦截器提示
    }
  } else {
    Object.assign(landingForm, {
      id: 0, name: '', type: 'mail', custom_path: '', html_content: '',
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
      custom_path: landingForm.custom_path.trim() || null,
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

// ============ 接口加载（失败保持空状态） ============
// 后端枚举值 → 前端筛选键归一化
const SCENE_TO_CAT: Record<string, string> = { system: 'upgrade', prize: 'lottery', security: 'alert' }
const PAGE_TYPE_TO_VIEW: Record<string, string> = {
  mail_login: 'mail', oa_login: 'oa', pan_auth: 'pan',
}
const ATTACH_TYPE_TO_VIEW: Record<string, string> = {
  benign_doc: 'other', macro_doc: 'macro',
}

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

// ============ AI 生成（草稿审核流：邮件模板/落地页/诱饵文档/企微消息） ============
const aiDrafts = ref<AiDraft[]>([])
// 各 Tab 只展示本类草稿，审核确认后统一刷新素材列表
const emailDrafts = computed(() => aiDrafts.value.filter(d => d.biz_type === 'email_template'))
const landingDrafts = computed(() => aiDrafts.value.filter(d => d.biz_type === 'landing_page'))
const payloadDrafts = computed(() => aiDrafts.value.filter(d => d.biz_type === 'attachment'))
const wecomDrafts = computed(() => aiDrafts.value.filter(d => d.biz_type === 'wecom_template'))

async function loadAiDrafts() {
  try {
    const list = await aiApi.drafts('draft')
    aiDrafts.value = list as AiDraft[]
  } catch {
    // 无 ai 菜单权限或加载失败时不打扰主流程（拦截器已提示）
  }
}

// ---- 邮件模板 ----
const aiGenVisible = ref(false)
const aiGenerating = ref(false)
const aiGenForm = reactive({ scene: 'finance', audience: '', tone: '正式', difficulty: 3 })

async function submitAiGen() {
  aiGenerating.value = true
  try {
    await aiApi.generateTemplate({ ...aiGenForm })
    aiGenVisible.value = false
    ElMessage.success('已生成草稿，审核通过后自动入库为模板')
    loadAiDrafts()
  } catch {
    // 失败提示由 http 拦截器统一弹出，保持弹窗打开可重试
  } finally {
    aiGenerating.value = false
  }
}

// ---- 落地页 ----
const aiLandingVisible = ref(false)
const aiLandingGenerating = ref(false)
const aiLandingForm = reactive({ scene: 'mail', company: '', audience: '', tone: '正式' })

async function submitAiLanding() {
  aiLandingGenerating.value = true
  try {
    await aiApi.generateLanding({ ...aiLandingForm })
    aiLandingVisible.value = false
    ElMessage.success('已生成落地页草稿，审核通过后自动入库')
    loadAiDrafts()
  } catch {
    // 失败提示由 http 拦截器统一弹出，保持弹窗打开可重试
  } finally {
    aiLandingGenerating.value = false
  }
}

// ---- 企微消息模板 ----
const aiWecomVisible = ref(false)
const aiWecomGenerating = ref(false)
const aiWecomForm = reactive({ scene: 'system', audience: '', tone: '正式' })

async function submitAiWecom() {
  aiWecomGenerating.value = true
  try {
    await aiApi.generateWecom({ ...aiWecomForm })
    aiWecomVisible.value = false
    ElMessage.success('已生成企微消息草稿，审核通过后自动入库')
    loadAiDrafts()
  } catch {
    // 失败提示由 http 拦截器统一弹出，保持弹窗打开可重试
  } finally {
    aiWecomGenerating.value = false
  }
}

// ---- 诱饵文档 ----
const aiPayloadVisible = ref(false)
const aiPayloadGenerating = ref(false)
const aiPayloadForm = reactive({ scene: '通知', audience: '', tone: '正式', doc_type: 'docx' })

async function submitAiPayload() {
  aiPayloadGenerating.value = true
  try {
    await aiApi.generateAttachment({ ...aiPayloadForm })
    aiPayloadVisible.value = false
    ElMessage.success('已生成诱饵文档草稿，审核通过后渲染文件入库')
    loadAiDrafts()
  } catch {
    // 失败提示由 http 拦截器统一弹出，保持弹窗打开可重试
  } finally {
    aiPayloadGenerating.value = false
  }
}

// ---- 草稿预览（按 biz_type 渲染） ----
interface AiPreviewItem {
  kind: string
  title: string
  name: string
  subject: string
  sender: string
  body: string
  html_content: string
  fieldsText: string
  description: string
  btn_text: string
  paragraphs: string[]
  table: { headers: string[]; rows: string[][] } | null
}
const aiPreviewVisible = ref(false)
const aiPreview = ref<AiPreviewItem | null>(null)

function parseAiDraft(d: AiDraft): AiPreviewItem | null {
  try {
    const m = JSON.parse(d.content || '{}')
    const fields = (m.form_schema?.fields || []) as { label?: string }[]
    return {
      kind: d.biz_type,
      title: m.title || m.name || d.title || '',
      name: m.name || '',
      subject: m.subject || d.title || '',
      sender: m.sender || '',
      body: m.body || '',
      html_content: m.html_content || '',
      fieldsText: fields.map(f => f.label || '').filter(Boolean).join(' / '),
      description: m.description || '',
      btn_text: m.btn_text || '查看详情',
      paragraphs: Array.isArray(m.paragraphs) ? m.paragraphs.map(String) : [],
      table: (m.table as { headers: string[]; rows: string[][] } | null) || null,
    }
  } catch {
    return null
  }
}

function previewAiDraft(d: AiDraft) {
  const p = parseAiDraft(d)
  if (!p) {
    ElMessage.warning('草稿内容解析失败')
    return
  }
  aiPreview.value = p
  aiPreviewVisible.value = true
}

async function approveAiDraft(d: AiDraft) {
  try {
    await aiApi.approveDraft(d.id)
    ElMessage.success('已确认入库')
    loadAiDrafts()
    loadTemplates()
    loadWecomTpls()
  } catch {
    // 无 ai:review 权限等由拦截器提示
  }
}

async function discardAiDraft(d: AiDraft) {
  try {
    await aiApi.discardDraft(d.id)
    loadAiDrafts()
  } catch {
    // 拦截器已提示
  }
}

onMounted(() => {
  loadTemplates()
  loadWecomTpls()
  loadAiDrafts()
})

// ============ 企业微信消息模板 ============
const WECOM_STATUS_TEXT = { approved: '已审核', draft: '草稿', discarded: '已驳回' }
interface WecomTplRow {
  id: number
  name: string
  msg_type: string
  title: string
  description: string
  btn_text: string
  url_mode: string
  custom_url: string
  status: string
  used_count: number
}
const wecomTplRows = ref<WecomTplRow[]>([])
const wecomTplLoading = ref(false)
const wecomTplSaving = ref(false)
const wecomTplDialogVisible = ref(false)
const wecomTplForm = reactive({
  id: 0,
  name: '',
  msg_type: 'textcard',
  title: '',
  description: '',
  btn_text: '查看详情',
  url_mode: 'track',
  custom_url: '',
  status: 'draft',
})

async function loadWecomTpls() {
  wecomTplLoading.value = true
  try {
    const list = await templateApi.wecomTemplates()
    if (Array.isArray(list)) wecomTplRows.value = list as WecomTplRow[]
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    wecomTplLoading.value = false
  }
}

function openWecomTplDialog(row?: WecomTplRow) {
  Object.assign(wecomTplForm, row
    ? {
        id: row.id, name: row.name, msg_type: row.msg_type, title: row.title,
        description: row.description, btn_text: row.btn_text, url_mode: row.url_mode,
        custom_url: row.custom_url, status: row.status,
      }
    : { id: 0, name: '', msg_type: 'textcard', title: '', description: '', btn_text: '查看详情', url_mode: 'track', custom_url: '', status: 'draft' })
  wecomTplDialogVisible.value = true
}

async function saveWecomTpl() {
  if (!wecomTplForm.name.trim()) {
    ElMessage.warning('请输入模板名称')
    return
  }
  if (!wecomTplForm.title.trim() || !wecomTplForm.description.trim()) {
    ElMessage.warning('请填写卡片标题与摘要')
    return
  }
  wecomTplSaving.value = true
  try {
    const payload = {
      name: wecomTplForm.name.trim(),
      msg_type: wecomTplForm.msg_type,
      title: wecomTplForm.title.trim(),
      description: wecomTplForm.description.trim(),
      btn_text: wecomTplForm.btn_text.trim() || '查看详情',
      url_mode: wecomTplForm.url_mode,
      custom_url: wecomTplForm.url_mode === 'custom' ? wecomTplForm.custom_url.trim() : null,
      // 注意：不带 status——审核状态只能经「审核」按钮（review 端点）流转
    }
    if (wecomTplForm.id) {
      await templateApi.updateWecomTemplate(wecomTplForm.id, payload)
    } else {
      await templateApi.createWecomTemplate(payload)
    }
    wecomTplDialogVisible.value = false
    ElMessage.success(wecomTplForm.id ? '模板已更新（改动后需重新审核）' : '模板已创建')
    await loadWecomTpls()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  } finally {
    wecomTplSaving.value = false
  }
}

async function reviewWecomTpl(row: WecomTplRow, status: 'approved' | 'discarded') {
  try {
    await templateApi.reviewWecomTemplate(row.id, status)
    ElMessage.success(status === 'approved' ? '模板已审核通过，可被演练选用' : '模板已驳回')
    await loadWecomTpls()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}

async function deleteWecomTpl(row: WecomTplRow) {
  try {
    await ElMessageBox.confirm(`确定删除企微消息模板「${row.name}」吗？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await templateApi.deleteWecomTemplate(row.id)
    ElMessage.success('模板已删除')
    await loadWecomTpls()
  } catch {
    // 失败提示由 http 拦截器统一弹出（被演练引用时后端拒绝）
  }
}

// 检测逃逸率配色：≥85 绿 / ≥70 黄 / 否则橙
function evadeColor(rate: number): string {
  if (rate >= 85) return 'var(--accent-green)'
  if (rate >= 70) return 'var(--accent-warning)'
  return 'var(--accent-orange)'
}

// 附件行操作（下载留审计；删除被演练引用时后端拒绝）
async function downloadPayload(row: PayloadItem) {
  try {
    await attachmentApi.download(row.id)
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
}
async function deletePayload(row: PayloadItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除附件「${row.name}」？已被演练引用时将被拒绝。`,
      '删除附件', { type: 'warning' },
    )
  } catch { return /* 用户取消 */ }
  try {
    await attachmentApi.remove(row.id)
    ElMessage.success('附件已删除')
    await loadTemplates()
  } catch {
    // 失败提示由 http 拦截器统一弹出（含引用保护错误）
  }
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

// 上传附件弹窗（一期良性文档；扩展名/大小前置校验，后端仍会二次拦截）
const uploadDialogVisible = ref(false)
const uploadRef = ref<UploadInstance>()
const uploadFile = ref<File | null>(null)

const ALLOWED_ATTACH_EXTS = ['docx', 'xlsx', 'pdf', 'zip']
const MAX_ATTACH_MB = 20

function openUploadDialog() {
  uploadFile.value = null
  uploadDialogVisible.value = true
}

function onUploadChange(file: UploadFile) {
  const raw = file.raw
  if (!raw) { uploadRef.value?.clearFiles(); return }
  const ext = (raw.name.split('.').pop() || '').toLowerCase()
  if (!ALLOWED_ATTACH_EXTS.includes(ext)) {
    ElMessage.warning('仅支持 docx/xlsx/pdf/zip 文档附件（宏/EXE 载荷未开放）')
    uploadRef.value?.clearFiles()
    return
  }
  if (raw.size > MAX_ATTACH_MB * 1024 * 1024) {
    ElMessage.warning(`附件大小超出限制（≤${MAX_ATTACH_MB}MB）`)
    uploadRef.value?.clearFiles()
    return
  }
  uploadFile.value = raw
}

function onUploadExceed() {
  ElMessage.warning('仅支持上传一个文件')
  uploadRef.value?.clearFiles()
}

async function submitUpload() {
  if (!uploadFile.value) { ElMessage.warning('请先选择文件'); return }
  try {
    await attachmentApi.upload(uploadFile.value)
    ElMessage.success(`附件「${uploadFile.value.name}」已上传`)
    uploadDialogVisible.value = false
    await loadTemplates()
  } catch {
    // 失败提示由 http 拦截器统一弹出
  }
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

// ===== AI 生成草稿 =====
.ai-draft-strip {
  margin-bottom: 14px;
  border: 1px dashed rgba(29, 158, 117, 0.35);
}
.ai-draft-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--color-text-tertiary);
  margin-left: 8px;
}
.tpl-preview-box {
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  padding: 16px;
  max-height: 480px;
  overflow: auto;
  background: #fff;
}
// 企微 textcard 卡片预览
.wecom-preview-box {
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  padding: 16px;
  max-width: 480px;
  margin: 0 auto;
}
.wecom-preview-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}
.wecom-preview-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}
.wecom-preview-btn {
  margin-top: 12px;
  text-align: center;
  border-top: 1px solid var(--color-background-tertiary);
  padding-top: 10px;
  color: #576b95;
  font-size: 13px;
}
// 诱饵文档表格预览
.doc-preview-table {
  border-collapse: collapse;
  margin: 12px auto;
  th, td {
    border: 1px solid #ccc;
    padding: 4px 10px;
    font-size: 12px;
  }
  th {
    background: var(--color-background-secondary);
    font-weight: 500;
  }
}
</style>
