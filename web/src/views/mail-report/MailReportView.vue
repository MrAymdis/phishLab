<template>
  <div class="page-container">
    <PageHeader title="邮件举报">
      <template #actions>
        <el-button size="small" :icon="Download" @click="downloadOutlookManifest">下载 Outlook 插件</el-button>
        <el-button size="small" :icon="Picture" @click="downloadWebmailZip">下载 Web 邮箱按钮</el-button>
        <el-button size="small" :icon="Setting" @click="activeTab = 'plugin'">API 配置说明</el-button>
        <el-button size="small" :icon="Refresh" @click="refreshAll">刷新</el-button>
      </template>
    </PageHeader>

    <el-tabs v-model="activeTab" style="margin: 8px 16px 0">
      <!-- ==================== 举报插件管理 ==================== -->
      <el-tab-pane label="举报插件管理" name="plugin">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="12">
            <div class="card card-blue plugin-card">
              <div class="plugin-header">
                <div class="plugin-icon outlook-icon">📧</div>
                <div class="plugin-title-wrap">
                  <div class="plugin-title">Outlook 桌面客户端插件</div>
                  <div class="plugin-sub">支持一键举报可疑邮件到安全运营中心</div>
                </div>
                <el-button type="primary" :icon="Download" @click="downloadOutlookManifest">下载</el-button>
              </div>
              <el-descriptions :column="2" size="small" border style="margin-top: 12px">
                <el-descriptions-item label="版本号">v1.2.0</el-descriptions-item>
                <el-descriptions-item label="更新日期">2026-08-31</el-descriptions-item>
                <el-descriptions-item label="形态">Office Web Add-in</el-descriptions-item>
                <el-descriptions-item label="部署方式">加载项 / 集中部署</el-descriptions-item>
              </el-descriptions>
              <div class="plugin-section">
                <div class="section-title">安装指引</div>
                <ol class="step-list">
                  <li>下载 <code>manifest.xml</code>（<b>已内置平台地址与通道密钥</b>）</li>
                  <li>Outlook：文件 → 管理加载项 → 我的加载项 → <b>添加自定义加载项</b>，选择 manifest.xml；企业走 Microsoft 365 管理中心集中部署，<b>员工安装即用、零配置</b></li>
                  <li>打开任意邮件，功能区出现「安全举报」按钮</li>
                  <li>点「举报可疑邮件」打开任务窗格（自动读取内置配置），按钮点两次确认提交</li>
                  <li>重生成 API Key 后需重新下载 manifest 并重发（集中部署重新上传）</li>
                </ol>
              </div>
              <div class="plugin-section">
                <div class="section-title">支持的邮箱客户端</div>
                <div class="tag-list">
                  <el-tag size="small">Outlook 2016+（Windows）</el-tag>
                  <el-tag size="small">Outlook 2016+（Mac）</el-tag>
                  <el-tag size="small">Outlook 365 桌面版</el-tag>
                </div>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="card card-green plugin-card">
              <div class="plugin-header">
                <div class="plugin-icon webmail-icon">🌐</div>
                <div class="plugin-title-wrap">
                  <div class="plugin-title">Web 邮箱举报按钮</div>
                  <div class="plugin-sub">通过浏览器书签/扩展在网页版邮箱举报</div>
                </div>
                <el-button type="primary" :icon="Picture" @click="downloadWebmailZip">下载</el-button>
              </div>
              <el-descriptions :column="2" size="small" border style="margin-top: 12px">
                <el-descriptions-item label="版本号">v1.1.0</el-descriptions-item>
                <el-descriptions-item label="更新日期">2026-08-31</el-descriptions-item>
                <el-descriptions-item label="形态">浏览器扩展（MV3）</el-descriptions-item>
                <el-descriptions-item label="支持浏览器">Chrome / Edge / Firefox</el-descriptions-item>
              </el-descriptions>
              <div class="plugin-section">
                <div class="section-title">安装指引</div>
                <ol class="step-list">
                  <li>下载 <code>phishlab-webmail-plugin.zip</code>（<b>已内置平台地址与通道密钥</b>）并解压</li>
                  <li>Chrome/Edge：<code>chrome://extensions</code> 开启开发者模式 → 加载已解压的扩展程序（Firefox：about:debugging 临时载入）</li>
                  <li>无需任何配置：扩展启动自动读取内置引导配置；若包内未内置，点工具栏图标导入「引导配置 JSON」</li>
                  <li>登录 Web 邮箱打开邮件，点击页面悬浮「举报」按钮一键提交</li>
                </ol>
              </div>
              <div class="plugin-section">
                <div class="section-title">支持的邮箱客户端</div>
                <div class="tag-list">
                  <el-tag size="small">企业微信邮箱</el-tag>
                  <el-tag size="small">钉钉邮箱</el-tag>
                  <el-tag size="small">飞书邮箱</el-tag>
                  <el-tag size="small">Outlook Web</el-tag>
                  <el-tag size="small">腾讯企业邮</el-tag>
                  <el-tag size="small">网易企业邮</el-tag>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-purple">
              <div class="card-title">举报 API 配置</div>
              <el-form label-width="140px" style="margin-top: 8px; max-width: 760px">
                <el-form-item label="API Endpoint">
                  <el-input :model-value="apiEndpoint" readonly>
                    <template #append>
                      <el-button :icon="CopyDocument" @click="copyText(apiEndpoint)">复制</el-button>
                    </template>
                  </el-input>
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input :model-value="pluginConfig.apiKeyMasked || '未生成'" readonly style="width: 320px">
                    <template #append>
                      <el-button :icon="RefreshRight" @click="doRegenKey">重生成</el-button>
                    </template>
                  </el-input>
                  <span style="margin-left: 10px; font-size: 11px; color: var(--color-text-tertiary)">插件鉴权密钥，加密存储仅回显掩码</span>
                </el-form-item>
                <el-form-item label="插件引导配置">
                  <el-button size="small" type="primary" :icon="Download" @click="downloadPluginConfig">下载引导配置 JSON</el-button>
                  <span style="margin-left: 10px; font-size: 11px; color: var(--color-text-tertiary)">含 serverUrl + 明文 API Key，插件首次使用导入；下载行为已记审计</span>
                </el-form-item>
                <el-form-item label="允许的域名列表">
                  <div class="domain-editor">
                    <el-tag v-for="d in pluginConfig.allowedDomains" :key="d" closable size="small" style="margin-right: 6px" @close="removeDomain(d)">
                      @{{ d }}
                    </el-tag>
                    <el-input v-model="domainInput" size="small" placeholder="输入域名后回车添加，如 company.com" style="width: 240px"
                      @keyup.enter="addDomain" />
                  </div>
                  <div style="font-size: 11px; color: var(--color-text-tertiary); margin-top: 4px">仅允许这些域名下的邮箱使用插件举报</div>
                </el-form-item>
                <el-form-item label="Webhook 回调 URL">
                  <el-input v-model="pluginConfig.webhookUrl" placeholder="https://soc.company.com/webhook/phish-report" />
                </el-form-item>
                <el-form-item label="自动分类">
                  <el-switch v-model="pluginConfig.autoclass" />
                  <span style="margin-left: 10px; font-size: 12px; color: var(--color-text-secondary)">开启后系统将自动识别举报邮件类型</span>
                </el-form-item>
                <el-form-item label="举报通知推送">
                  <el-checkbox v-model="pluginConfig.notifyChannels.wecom">企业微信</el-checkbox>
                  <el-checkbox v-model="pluginConfig.notifyChannels.dingtalk">钉钉</el-checkbox>
                  <el-checkbox v-model="pluginConfig.notifyChannels.feishu">飞书</el-checkbox>
                  <span style="margin-left: 8px; font-size: 11px; color: var(--color-text-tertiary)">真实钓鱼举报将即时推送到所选平台（二期）</span>
                </el-form-item>
              </el-form>
              <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; padding-top: 14px; border-top: 1px solid var(--color-border-tertiary); max-width: 760px">
                <el-button size="small" @click="doTestWebhook">测试连接</el-button>
                <el-button size="small" type="primary" @click="doSavePluginConfig">保存配置</el-button>
              </div>
              <div class="code-section">
                <div class="section-title">
                  接入代码示例（cURL）
                  <el-button size="small" link type="primary" :icon="CopyDocument" @click="copyText(codeSample)">复制代码</el-button>
                </div>
                <pre class="code-block"><code>{{ codeSample }}</code></pre>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- ==================== 举报中心 ==================== -->
      <el-tab-pane label="举报中心" name="center">
        <el-row :gutter="12" style="margin: 16px 0 0">
          <el-col :span="24">
            <div class="card card-blue">
              <div class="toolbar">
                <el-date-picker
                  v-model="reportDateRange"
                  type="daterange"
                  size="small"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  value-format="YYYY-MM-DD"
                />
                <el-select v-model="reportCategory" size="small" placeholder="全部分类" style="width: 160px" @change="reloadReports">
                  <el-option label="全部" value="" />
                  <el-option label="演练钓鱼" value="drill" />
                  <el-option label="真实钓鱼" value="real" />
                  <el-option label="误报" value="false" />
                  <el-option label="待研判" value="pending" />
                </el-select>
                <el-input v-model="reportKw" size="small" placeholder="搜索主题/发件人/举报人" style="width: 280px" clearable @keyup.enter="reloadReports" @clear="reloadReports" />
                <el-button size="small" type="primary" @click="reloadReports">查询</el-button>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 0">
          <el-col :span="6"><StatCard title="累计举报量" :value="reportStats.total" suffix=" 封" accent="blue" /></el-col>
          <el-col :span="6"><StatCard title="本月举报" :value="reportStats.monthCount" suffix=" 封" accent="teal" /></el-col>
          <el-col :span="6"><StatCard title="真实钓鱼数" :value="reportStats.realCount" suffix=" 封" accent="red" /></el-col>
          <el-col :span="6"><StatCard title="误报率" :value="reportStats.misreportRate" suffix=" %" accent="orange" /></el-col>
        </el-row>

        <el-row :gutter="12" style="margin: 12px 0 16px">
          <el-col :span="24">
            <div class="card card-teal">
              <div class="card-title">举报记录</div>
              <el-table :data="reportRows" size="small" style="margin-top: 8px" v-loading="reportLoading">
                <el-table-column label="时间" prop="time" width="160" />
                <el-table-column label="邮件主题" prop="subject" min-width="220" show-overflow-tooltip />
                <el-table-column label="发件人" prop="sender" min-width="180" show-overflow-tooltip />
                <el-table-column label="举报人" width="160">
                  <template #default="{ row }">
                    <div>
                      <div>{{ row.reporter }}</div>
                      <div style="font-size: 11px; color: var(--color-text-tertiary)">{{ row.reporterDept }}</div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="自动分类结果" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.auto === 'drill'" type="primary" size="small">演练钓鱼</el-tag>
                    <el-tag v-else-if="row.auto === 'real'" type="danger" size="small">真实钓鱼</el-tag>
                    <el-tag v-else-if="row.auto === 'false'" type="info" size="small">误报</el-tag>
                    <el-tag v-else type="warning" size="small">待研判</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="人工复核结果" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.manual === 'real'" type="danger" size="small">真实钓鱼</el-tag>
                    <el-tag v-else-if="row.manual === 'false'" type="info" size="small">误报</el-tag>
                    <el-tag v-else-if="row.manual === 'drill'" type="primary" size="small">演练</el-tag>
                    <span v-else style="color: var(--color-text-tertiary); font-size: 12px">待复核</span>
                  </template>
                </el-table-column>
                <el-table-column label="积分" prop="rewardPoints" width="70" align="center" />
                <el-table-column label="操作" width="280" fixed="right">
                  <template #default="{ row }">
                    <el-button link size="small" type="primary" @click="openDetailDialog(row)">详情</el-button>
                    <el-button link size="small" type="danger" @click="openRealDialog(row)" v-if="!row.manual">研判为真实钓鱼</el-button>
                    <el-button link size="small" v-if="!row.manual" @click="classifyReport(row, 'false_positive')">标记误报</el-button>
                    <el-button link size="small" type="success" @click="openPushSoc(row)">推送SOC</el-button>
                  </template>
                </el-table-column>
                <template #empty><el-empty description="暂无举报记录" :image-size="70" /></template>
              </el-table>
              <el-pagination
                style="margin-top: 12px; justify-content: flex-end"
                layout="total, sizes, prev, pager, next"
                :total="reportTotal"
                v-model:current-page="reportPage"
                v-model:page-size="reportPageSize"
                :page-sizes="[10, 20, 50, 100]"
                @current-change="loadReports"
                @size-change="reloadReports"
              />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- ==================== 举报奖励 ==================== -->
      <el-tab-pane label="举报奖励" name="reward">
        <el-row :gutter="12" style="margin: 16px 0 16px">
          <el-col :span="14">
            <div class="card card-orange">
              <div class="card-title">🏆 积分排行榜 · TOP 20（本月）</div>
              <el-table :data="rankRows" size="small" style="margin-top: 8px">
                <el-table-column label="排名" width="70" align="center">
                  <template #default="{ row }">
                    <span v-if="row.rank === 1" class="medal gold">🏆</span>
                    <span v-else-if="row.rank === 2" class="medal silver">🥈</span>
                    <span v-else-if="row.rank === 3" class="medal bronze">🥉</span>
                    <span v-else style="color: var(--color-text-secondary)">{{ row.rank }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="姓名" prop="name" width="110" />
                <el-table-column label="部门" prop="dept" width="130" />
                <el-table-column label="本月举报" prop="reportCount" width="90" align="center" />
                <el-table-column label="本月积分" width="100" align="center">
                  <template #default="{ row }">
                    <span style="font-weight: 600">{{ row.monthPoints }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="累计积分" width="100" align="center">
                  <template #default="{ row }">{{ row.totalPoints }}</template>
                </el-table-column>
                <el-table-column label="徽章" align="center">
                  <template #default="{ row }">
                    <el-tag v-for="b in row.badges" :key="b" size="small" effect="dark" style="margin-right: 4px; background: linear-gradient(135deg, #F59E0B, #D97706); border: none">{{ b }}</el-tag>
                  </template>
                </el-table-column>
                <template #empty><el-empty description="暂无积分记录" :image-size="70" /></template>
              </el-table>
            </div>

            <div class="card card-green" style="margin-top: 12px">
              <div class="card-title">
                积分规则说明
                <el-button size="small" link type="primary" @click="openRulesDialog">编辑规则</el-button>
              </div>
              <ul class="rule-list">
                <li v-for="r in rewardRules" :key="r.type">
                  <el-tag size="small" :type="ruleTagType(r.type)">+{{ r.points }}</el-tag>
                  <b style="font-size: 13px">{{ r.name }}</b>
                  <span style="font-size: 12px; color: var(--color-text-secondary)">{{ r.desc }}</span>
                </li>
              </ul>
            </div>
          </el-col>
          <el-col :span="10">
            <div class="card card-blue">
              <div class="card-title">平台积分概览</div>
              <div class="my-points">
                <div class="points-row">
                  <div class="points-item">
                    <div class="points-label">累计发放积分</div>
                    <div class="points-value total">{{ pointsOverview.totalIssued }}</div>
                  </div>
                  <div class="points-item">
                    <div class="points-label">本月发放</div>
                    <div class="points-value month">{{ pointsOverview.monthIssued }}</div>
                  </div>
                  <div class="points-item">
                    <div class="points-label">参与举报人数</div>
                    <div class="points-value month">{{ pointsOverview.participants }}</div>
                  </div>
                </div>
                <div class="history-section">
                  <div class="section-title">最近兑换记录</div>
                  <div v-for="h in pointsOverview.redemptions" :key="h.id" class="history-row">
                    <span>{{ h.time }}</span><span>{{ h.user }} · {{ h.item }}</span><span style="color: #10B981">-{{ h.points }}分</span>
                  </div>
                  <el-empty v-if="!pointsOverview.redemptions.length" description="暂无兑换记录" :image-size="40" />
                </div>
              </div>
            </div>

            <div class="card card-red" style="margin-top: 12px">
              <div class="card-title">奖励兑换中心</div>
              <el-select
                v-model="redeemUserId"
                filterable
                remote
                clearable
                size="small"
                :remote-method="searchRedeemUsers"
                :loading="redeemUserLoading"
                placeholder="搜索并选择兑换员工"
                style="width: 100%; margin-bottom: 8px"
              >
                <el-option v-for="u in redeemUserCandidates" :key="u.id" :label="u.label" :value="u.id" />
              </el-select>
              <div v-for="item in catalogItems" :key="item.id" class="reward-item">
                <div class="reward-icon">{{ item.icon || '🎁' }}</div>
                <div class="reward-info">
                  <div class="reward-name">{{ item.name }}</div>
                  <div class="reward-cost" v-if="item.cost > 0">需要 <b>{{ item.cost }}</b> 积分（库存 {{ item.stock }}）</div>
                  <div class="reward-cost" v-else>进入季度 Top 20 自动发放（免费）</div>
                </div>
                <el-button size="small" type="danger" :disabled="item.cost <= 0 || item.stock <= 0" @click="doRedeem(item)">兑换</el-button>
              </div>
              <el-empty v-if="!catalogItems.length" description="暂无兑换商品" :image-size="50" />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="realDialogVisible" title="真实钓鱼研判处置" width="520px">
      <div style="margin-bottom: 12px">
        <div style="font-size: 13px; color: var(--color-text-secondary); margin-bottom: 8px">
          邮件：<b style="color: var(--color-text-primary)">{{ currentReport?.subject }}</b>
        </div>
        <div style="font-size: 13px; color: var(--color-text-secondary)">
          发件人：<b style="color: var(--color-text-primary)">{{ currentReport?.sender }}</b>
        </div>
      </div>
      <el-form label-width="100px">
        <el-form-item label="处置选择">
          <el-checkbox-group v-model="disposalOptions">
            <el-checkbox value="push_soc">推送 SOC / SIEM</el-checkbox>
            <el-checkbox value="quarantine">隔离邮件（全邮箱搜索）</el-checkbox>
            <el-checkbox value="trace">启动溯源分析</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="处置备注">
          <el-input v-model="disposalRemark" type="textarea" :rows="3" placeholder="可选：记录研判依据、关联事件等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="realDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitRealDisposal">确认提交处置</el-button>
      </template>
    </el-dialog>

    <!-- ============ 举报详情弹窗 ============ -->
    <el-dialog v-model="detailDialogVisible" title="举报详情" width="780px" destroy-on-close>
      <template v-if="currentReport">
        <!-- 举报人信息 -->
        <el-descriptions :column="4" size="small" border>
          <el-descriptions-item label="举报人">{{ currentReport.reporter }}</el-descriptions-item>
          <el-descriptions-item label="部门">{{ currentReport.reporterDept }}</el-descriptions-item>
          <el-descriptions-item label="举报时间">{{ currentReport.time }}</el-descriptions-item>
          <el-descriptions-item label="举报渠道">{{ channelLabel(currentReport.channel) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 邮件预览 -->
        <div class="card" style="margin-top: 14px; border-top-color: var(--accent-red)">
          <div class="card-title">
            邮件预览
            <el-button v-if="emlPreview.hasEml" size="small" link type="primary" @click="downloadEml(currentReport!.id)">
              下载 EML 原件（{{ formatBytes(emlPreview.emlSize) }}）
            </el-button>
          </div>
          <div class="mail-meta">
            <div class="mail-meta-row"><span class="mail-meta-label">发件人</span><span class="mail-meta-value danger">{{ emlPreview.from || currentReport.sender || '（未上报）' }}</span></div>
            <div class="mail-meta-row"><span class="mail-meta-label">主题</span><span class="mail-meta-value"><b>{{ emlPreview.subject || currentReport.subject }}</b></span></div>
            <div class="mail-meta-row"><span class="mail-meta-label">收件人</span><span class="mail-meta-value">{{ emlPreview.to || '（未上报）' }}</span></div>
            <div class="mail-meta-row"><span class="mail-meta-label">时间</span><span class="mail-meta-value">{{ emlPreview.date || '（未上报）' }}</span></div>
            <div class="mail-meta-row"><span class="mail-meta-label">Message-ID</span><span class="mail-meta-value">{{ currentReport.messageId || '（未上报）' }}</span></div>
          </div>
          <el-divider style="margin: 10px 0" />
          <pre v-if="emlPreview.body" class="body-preview">{{ emlPreview.body }}</pre>
          <el-empty v-else :description="emlPreview.hasEml ? '该邮件无正文文本' : '邮件正文未归档（Web 邮箱/旧版客户端仅上报元数据）'" :image-size="50" />
        </div>

        <!-- 附件列表 -->
        <div class="card" style="margin-top: 12px">
          <div class="card-title">附件列表</div>
          <el-table v-if="emlPreview.attachments.length" :data="emlPreview.attachments" size="small" style="margin-top: -4px">
            <el-table-column label="附件名" prop="name" min-width="220" show-overflow-tooltip />
            <el-table-column label="大小" width="100" align="right">
              <template #default="{ row }">{{ formatBytes(row.size) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else :description="emlPreview.hasEml ? '该邮件无附件' : 'EML 附件未上传（仅元数据上报）'" :image-size="40" />
        </div>

        <!-- 邮件头详情 -->
        <div class="card" style="margin-top: 12px">
          <el-collapse v-model="headerCollapse">
            <el-collapse-item title="邮件头详情（溯源分析）" name="headers">
              <div v-for="h in detailHeaders" :key="h.key" class="header-row">
                <span class="header-key">{{ h.key }}</span>
                <span class="header-val">{{ h.value }}</span>
              </div>
              <el-empty v-if="!detailHeaders.length" description="邮件头未上报（Web 邮箱/旧版客户端仅上报元数据）" :image-size="40" />
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 处理操作 -->
        <div class="card card-teal" style="margin-top: 12px">
          <div class="card-title">处理操作</div>
          <el-radio-group v-model="detailAction" size="small">
            <el-radio-button value="drill">判定为演练邮件</el-radio-button>
            <el-radio-button value="real">判定为真实钓鱼</el-radio-button>
            <el-radio-button value="false">判定为误报</el-radio-button>
          </el-radio-group>
          <el-input v-model="detailRemark" type="textarea" :rows="2" placeholder="处理备注（可选）" style="margin-top: 10px" />
        </div>
      </template>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="submitDetailAction">提交处理结果</el-button>
      </template>
    </el-dialog>

    <!-- ============ 编辑积分规则弹窗 ============ -->
    <el-dialog v-model="rulesDialogVisible" title="编辑积分规则" width="620px">
      <el-table :data="rulesDraft" size="small">
        <el-table-column label="举报类型" prop="name" width="140" />
        <el-table-column label="奖励积分" width="150">
          <template #default="{ row }">
            <el-input-number v-model="row.points" :min="0" :max="10000" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="说明" prop="desc" min-width="220" show-overflow-tooltip />
      </el-table>
      <div style="font-size: 11px; color: var(--color-text-tertiary); margin-top: 8px">💡 修改后即时生效；连续举报=每第 3 次正确举报额外奖励</div>
      <template #footer>
        <el-button @click="rulesDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doSaveRules">保存规则</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Picture, Setting, Refresh, CopyDocument, RefreshRight } from '@element-plus/icons-vue'
import PageHeader from '@/components/base/PageHeader.vue'
import StatCard from '@/components/base/StatCard.vue'
import { reportApi, orgApi } from '@/api'
import { downloadFile } from '@/api/http'

const activeTab = ref('plugin')
// 插件资产公开托管；base 传浏览器可见 origin（反代改写 Host 时 request.base_url 不可达）
// Outlook 硬性要求 manifest 内所有 URL 为 https://（http 连 localhost 都不豁免）——http 访问直接拦截引导，避免下载必被拒的清单
const downloadOutlookManifest = () => {
  if (location.protocol !== 'https:') {
    ElMessageBox.alert(
      `Outlook 要求加载项清单内所有地址必须为 https://，当前管理端以 http 访问，生成的清单会被拒绝安装。` +
        `请改用 https://${location.hostname}${location.port ? ':' + location.port : ''}${location.pathname} 访问管理端后重新下载` +
        `（自签证书浏览器会提示不安全，继续访问即可）。`,
      '需要 HTTPS 访问',
      { type: 'warning', confirmButtonText: '知道了' },
    )
    return
  }
  downloadFile(`/api/v1/mail-reports/plugin-config/outlook-manifest?base=${encodeURIComponent(location.origin)}`)
}
// 内置引导配置版（员工零配置）：鉴权端点，包内预置 phishlab-guide.json；公开 zip 供手工导入流程备用
const downloadWebmailZip = () =>
  downloadFile(`/api/v1/mail-reports/plugin-config/webmail-package?base=${encodeURIComponent(location.origin)}`)
const downloadPluginConfig = () =>
  downloadFile(`/api/v1/mail-reports/plugin-config/export?base=${encodeURIComponent(location.origin)}`)

// ============ 举报插件管理 ============
const apiEndpoint = computed(() => `${location.origin}/report/v1/mail`)
const pluginConfig = reactive({
  apiKeyMasked: '',
  allowedDomains: [] as string[],
  webhookUrl: '',
  autoclass: true,
  notifyChannels: { wecom: true, dingtalk: false, feishu: true },
})
const domainInput = ref('')

const codeSample = computed(() => `curl -X POST ${apiEndpoint.value} \\
  -H "X-Api-Key: <插件API Key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "reporter_email": "zhangsan@company.com",
    "subject": "【紧急】工资条更新通知",
    "from_addr": "hr-department@phishing.com",
    "message_id": "<...>",
    "headers": "Return-Path: <...>\\n..."
  }'`)

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

function addDomain() {
  const d = domainInput.value.trim().toLowerCase().replace(/^@/, '')
  if (!d) return
  if (d.includes('@') || d.includes('/')) { ElMessage.warning('请输入纯域名，如 company.com'); return }
  if (!pluginConfig.allowedDomains.includes(d)) pluginConfig.allowedDomains.push(d)
  domainInput.value = ''
}
function removeDomain(d: string) {
  pluginConfig.allowedDomains = pluginConfig.allowedDomains.filter(x => x !== d)
}

async function loadPluginConfig() {
  try {
    const res = (await reportApi.pluginConfig()) as Record<string, any>
    Object.assign(pluginConfig, {
      apiKeyMasked: res.apiKeyMasked || '',
      allowedDomains: Array.isArray(res.allowedDomains) ? res.allowedDomains : [],
      webhookUrl: res.webhookUrl || '',
      autoclass: res.autoclass !== false,
      notifyChannels: { wecom: true, dingtalk: false, feishu: true, ...(res.notifyChannels || {}) },
    })
  } catch { /* 拦截器已提示 */ }
}

async function doSavePluginConfig() {
  try {
    await reportApi.updatePluginConfig({
      allowedDomains: pluginConfig.allowedDomains,
      webhookUrl: pluginConfig.webhookUrl,
      autoclass: pluginConfig.autoclass,
      notifyChannels: pluginConfig.notifyChannels,
    })
    ElMessage.success('插件配置已保存')
  } catch { /* 拦截器已提示 */ }
}

async function doRegenKey() {
  try {
    await ElMessageBox.confirm('重生成后旧 Key 立即失效，插件需同步更新，确认继续？', '重生成 API Key', { type: 'warning' })
  } catch { return }
  try {
    const res = (await reportApi.regenPluginKey()) as { apiKeyMasked: string }
    pluginConfig.apiKeyMasked = res.apiKeyMasked
    ElMessage.success('API Key 已重生成')
  } catch { /* 拦截器已提示 */ }
}

async function doTestWebhook() {
  try {
    const res = (await reportApi.testPluginWebhook(pluginConfig.webhookUrl)) as { ok: boolean; status: number; message: string }
    if (res.ok) ElMessage.success(`连接成功：${res.message}`)
    else ElMessage.warning(`连接失败：${res.message}`)
  } catch { /* 拦截器已提示 */ }
}

// ============ 举报中心 ============
const reportDateRange = ref<[string, string] | null>(null)
const reportCategory = ref('')
const reportKw = ref('')
const reportRows = ref<any[]>([])
const reportTotal = ref(0)
const reportPage = ref(1)
const reportPageSize = ref(20)
const reportLoading = ref(false)
const reportStats = reactive({ total: 0, monthCount: 0, realCount: 0, falseCount: 0, misreportRate: 0 })

const classificationMap: Record<string, string> = { drill: 'drill', real: 'real_phishing', false: 'false_positive', pending: 'pending' }

async function loadReports() {
  reportLoading.value = true
  try {
    const q: Record<string, unknown> = { page: reportPage.value, pageSize: reportPageSize.value }
    if (reportCategory.value) q.classification = classificationMap[reportCategory.value] ?? reportCategory.value
    if (reportKw.value.trim()) q.kw = reportKw.value.trim()
    if (reportDateRange.value) {
      q.start_date = reportDateRange.value[0]
      q.end_date = reportDateRange.value[1]
    }
    const res = (await reportApi.list(q)) as { list: any[]; total: number }
    reportRows.value = res.list ?? []
    reportTotal.value = res.total ?? 0
  } catch { /* 拦截器已提示 */ } finally {
    reportLoading.value = false
  }
}
const reloadReports = () => { reportPage.value = 1; loadReports() }

async function loadReportStats() {
  try {
    const res = (await reportApi.stats()) as Record<string, any>
    Object.assign(reportStats, res)
  } catch { /* 拦截器已提示 */ }
}

async function classifyReport(row: any, classification: string, remark?: string): Promise<boolean> {
  try {
    const res = (await reportApi.classify(row.id, classification, remark)) as { points?: number }
    ElMessage.success(res.points ? `研判已提交，发放 ${res.points} 积分` : '研判结果已提交')
    loadReports()
    loadReportStats()
    return true
  } catch {
    return false
  }
}

const realDialogVisible = ref(false)
const currentReport = ref<any>(null)
const disposalOptions = ref<string[]>([])
const disposalRemark = ref('')

const openRealDialog = (row: any) => {
  currentReport.value = row
  disposalOptions.value = []
  disposalRemark.value = ''
  realDialogVisible.value = true
}

const openPushSoc = (row: any) => {
  currentReport.value = row
  disposalOptions.value = ['push_soc']
  disposalRemark.value = ''
  realDialogVisible.value = true
}

const submitRealDisposal = async () => {
  if (!currentReport.value) return
  const remark = [disposalOptions.value.length ? `处置：${disposalOptions.value.join('/')}` : '', disposalRemark.value].filter(Boolean).join('；')
  const ok = await classifyReport(currentReport.value, 'real_phishing', remark)
  if (ok) realDialogVisible.value = false
}

// ============ 举报详情弹窗 ============
const detailDialogVisible = ref(false)
const headerCollapse = ref<string[]>(['headers'])
const detailAction = ref('drill')
const detailRemark = ref('')

const channelLabel = (c: string) =>
  ({ outlook_plugin: 'Outlook 插件', webmail: 'Web 邮箱', manual: '手工登记', api: 'API 接入' } as Record<string, string>)[c] || c || '（未知）'

function parseHeaders(raw: string) {
  if (!raw) return []
  return raw.split(/\r?\n/).filter(l => l.trim()).map(line => {
    const i = line.indexOf(':')
    return i > 0
      ? { key: line.slice(0, i).trim(), value: line.slice(i + 1).trim() }
      : { key: line.trim(), value: '' }
  })
}
const detailHeaders = computed(() => parseHeaders(currentReport.value?.headers || ''))

// EML 归档预览：hasEml → 拉取 /preview 解析结果；否则保持空态占位
const emlPreview = reactive({
  hasEml: false,
  emlSize: 0,
  from: '',
  subject: '',
  to: '',
  date: '',
  body: '',
  attachments: [] as { name: string; size: number }[],
})

function resetEmlPreview(hasEml: boolean) {
  Object.assign(emlPreview, { hasEml, emlSize: 0, from: '', subject: '', to: '', date: '', body: '', attachments: [] })
}

async function loadEmlPreview(rid: number) {
  try {
    Object.assign(emlPreview, await reportApi.preview(rid))
  } catch {
    resetEmlPreview(false) // 加载失败回落元数据占位（拦截器已提示）
  }
}

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

function downloadEml(rid: number) {
  downloadFile(`/api/v1/mail-reports/${rid}/eml`)
}

const openDetailDialog = (row: any) => {
  currentReport.value = row
  detailAction.value = row.manual || 'drill'
  detailRemark.value = ''
  detailDialogVisible.value = true
  if (row.hasEml) loadEmlPreview(row.id)
  else resetEmlPreview(false)
}

const detailActionMap: Record<string, string> = { drill: 'drill', real: 'real_phishing', false: 'false_positive' }

const submitDetailAction = async () => {
  if (!currentReport.value) return
  const ok = await classifyReport(currentReport.value, detailActionMap[detailAction.value], detailRemark.value)
  if (ok) detailDialogVisible.value = false
}

// ============ 举报奖励 ============
const rankRows = ref<any[]>([])
const rewardRules = ref<{ type: string; name: string; points: number; desc: string }[]>([])
const pointsOverview = reactive({ totalIssued: 0, monthIssued: 0, participants: 0, redemptions: [] as any[] })
const catalogItems = ref<{ id: number; name: string; icon: string; cost: number; stock: number }[]>([])
const redeemUserId = ref<number | null>(null)
const redeemUserCandidates = ref<{ id: number; label: string }[]>([])
const redeemUserLoading = ref(false)

const ruleTagType = (t: string) =>
  ({ drill: 'primary', real: 'danger', first: 'success', streak: 'warning' } as Record<string, string>)[t] || 'info'

async function loadRanking() {
  try {
    const res = (await reportApi.ranking()) as { list: any[] }
    rankRows.value = res.list ?? []
  } catch { /* 拦截器已提示 */ }
}

async function loadRewardRules() {
  try {
    const res = (await reportApi.rewardRules()) as { rules: typeof rewardRules.value }
    rewardRules.value = res.rules ?? []
  } catch { /* 拦截器已提示 */ }
}

const rulesDialogVisible = ref(false)
const rulesDraft = ref<{ type: string; name: string; points: number; desc: string }[]>([])
const openRulesDialog = () => {
  rulesDraft.value = rewardRules.value.map(r => ({ ...r }))
  rulesDialogVisible.value = true
}
async function doSaveRules() {
  try {
    await reportApi.updateRewardRules(rulesDraft.value as Record<string, unknown>[])
    ElMessage.success('积分规则已保存')
    rulesDialogVisible.value = false
    loadRewardRules()
  } catch { /* 拦截器已提示 */ }
}

async function loadPointsOverview() {
  try {
    const res = (await reportApi.pointsOverview()) as Record<string, any>
    pointsOverview.totalIssued = res.totalIssued ?? 0
    pointsOverview.monthIssued = res.monthIssued ?? 0
    pointsOverview.participants = res.participants ?? 0
    pointsOverview.redemptions = res.redemptions ?? []
  } catch { /* 拦截器已提示 */ }
}

async function loadCatalog() {
  try {
    const res = (await reportApi.rewardCatalog()) as { items: typeof catalogItems.value }
    catalogItems.value = res.items ?? []
  } catch { /* 拦截器已提示 */ }
}

async function searchRedeemUsers(kw: string) {
  if (!kw) { redeemUserCandidates.value = []; return }
  redeemUserLoading.value = true
  try {
    const res = (await orgApi.users({ kw, page: 1, pageSize: 20 })) as { list: any[] }
    redeemUserCandidates.value = (res?.list ?? []).map(u => ({
      id: u.id,
      label: `${u.name}（${u.no || u.email} · ${u.deptShort || ''}）`,
    }))
  } catch {
    redeemUserCandidates.value = []
  } finally {
    redeemUserLoading.value = false
  }
}

async function doRedeem(item: { id: number; name: string; cost: number; stock: number }) {
  if (!redeemUserId.value) { ElMessage.warning('请先搜索并选择兑换员工'); return }
  try {
    await ElMessageBox.confirm(
      `确认为所选员工兑换「${item.name}」？将扣除 ${item.cost} 积分（库存 ${item.stock}）`,
      '兑换确认', { type: 'warning', confirmButtonText: '确认兑换' },
    )
  } catch { return }
  try {
    await reportApi.redeem(redeemUserId.value, item.id)
    ElMessage.success('兑换成功，已扣除积分')
    loadPointsOverview()
    loadCatalog()
    loadRanking()
  } catch { /* 拦截器已提示 */ }
}

// ============ tab 懒加载 ============
const loadedTabs = reactive<Record<string, boolean>>({})
function ensureTabLoaded(tab: string) {
  if (loadedTabs[tab]) return
  loadedTabs[tab] = true
  if (tab === 'plugin') loadPluginConfig()
  else if (tab === 'center') { loadReportStats(); loadReports() }
  else if (tab === 'reward') { loadRanking(); loadRewardRules(); loadPointsOverview(); loadCatalog() }
}

function refreshAll() {
  const tab = activeTab.value
  if (tab === 'plugin') loadPluginConfig()
  else if (tab === 'center') { loadReportStats(); loadReports() }
  else if (tab === 'reward') { loadRanking(); loadRewardRules(); loadPointsOverview(); loadCatalog() }
}

watch(activeTab, (tab) => ensureTabLoaded(tab))
onMounted(() => ensureTabLoaded(activeTab.value))
</script>

<style scoped lang="scss">
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.plugin-card {
  height: 100%;
}
.plugin-header {
  display: flex;
  align-items: center;
  gap: 14px;
}
.plugin-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  flex-shrink: 0;
}
.outlook-icon {
  background: linear-gradient(135deg, #378ADD22, #378ADD55);
}
.webmail-icon {
  background: linear-gradient(135deg, #10B98122, #10B98155);
}
.plugin-title-wrap {
  flex: 1;
}
.plugin-title {
  font-size: 15px;
  font-weight: 600;
}
.plugin-sub {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.plugin-section {
  margin-top: 16px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.step-list {
  padding-left: 20px;
  margin: 0;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 2;
  code {
    background: var(--color-background-secondary);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
  }
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.code-section {
  margin-top: 20px;
}
.code-block {
  margin: 8px 0 0;
  background: #1e293b;
  color: #e2e8f0;
  padding: 14px 16px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.65;
  overflow-x: auto;
}
.domain-editor {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  padding: 6px 8px;
  min-height: 34px;
  min-width: 400px;
}
.medal {
  font-size: 18px;
}
.rule-list {
  list-style: none;
  padding: 0;
  margin: 0;
  li {
    padding: 8px 0;
    border-bottom: 1px dashed var(--color-border-tertiary);
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 10px;
    &:last-child { border-bottom: none; }
  }
}
.my-points {
  .points-row {
    display: flex;
    gap: 12px;
    margin: 4px 0 16px;
  }
  .points-item {
    flex: 1;
    text-align: center;
    padding: 12px;
    background: var(--color-background-secondary);
    border-radius: 10px;
  }
  .points-label {
    font-size: 12px;
    color: var(--color-text-secondary);
  }
  .points-value {
    font-size: 24px;
    font-weight: 600;
    margin-top: 4px;
    &.total { color: #378ADD; }
    &.month { color: #10B981; }
  }
}
.history-section {
  .section-title { margin-bottom: 6px; }
}
.history-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  padding: 6px 0;
  color: var(--color-text-secondary);
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border-bottom: none; }
}
.reward-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
}
.reward-icon {
  width: 44px;
  height: 44px;
  background: var(--color-background-secondary);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.reward-info {
  flex: 1;
}
.reward-name {
  font-size: 13px;
  font-weight: 600;
}
.reward-cost {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}
.mail-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mail-meta-row {
  display: flex;
  gap: 10px;
  font-size: 12px;
}
.mail-meta-label {
  width: 80px;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.body-preview {
  margin: 0;
  max-height: 260px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--color-text-primary);
  background: var(--color-fill-light, #f7f8fa);
  padding: 10px 12px;
  border-radius: 6px;
}
.mail-meta-value {
  color: var(--color-text-primary);
  word-break: break-all;
  &.danger { color: #f56c6c; font-weight: 600; }
}
.header-row {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 12px;
  border-bottom: 1px dashed var(--color-border-tertiary);
  &:last-child { border-bottom: none; }
}
.header-key {
  width: 110px;
  flex-shrink: 0;
  font-weight: 600;
  color: var(--color-text-secondary);
  font-family: monospace;
}
.header-val {
  flex: 1;
  color: var(--color-text-primary);
  font-family: monospace;
  word-break: break-all;
}
</style>
