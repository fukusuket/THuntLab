import jenkins.model.*
import hudson.security.*
import jenkins.security.s2m.AdminWhitelistRule

def instance = Jenkins.getInstance()

def authStrategy = new hudson.security.GlobalMatrixAuthorizationStrategy()
authStrategy.add(Jenkins.ADMINISTER, "anonymous")
authStrategy.add(Jenkins.READ, "anonymous")
authStrategy.add(Item.BUILD, "anonymous")
authStrategy.add(Item.CONFIGURE, "anonymous")
authStrategy.add(Item.CREATE, "anonymous")
authStrategy.add(Item.DELETE, "anonymous")
authStrategy.add(Item.DISCOVER, "anonymous")
authStrategy.add(Item.READ, "anonymous")
authStrategy.add(Item.WORKSPACE, "anonymous")
authStrategy.add(View.CONFIGURE, "anonymous")
authStrategy.add(View.CREATE, "anonymous")
authStrategy.add(View.DELETE, "anonymous")
authStrategy.add(View.READ, "anonymous")
authStrategy.add(Run.DELETE, "anonymous")
authStrategy.add(Run.UPDATE, "anonymous")
authStrategy.add(SCM.TAG, "anonymous")

instance.setAuthorizationStrategy(authStrategy)
instance.setSecurityRealm(SecurityRealm.NO_AUTHENTICATION)
instance.setCrumbIssuer(null)
instance.getInjector().getInstance(AdminWhitelistRule.class).setMasterKillSwitch(false)

instance.save()
println "Security disabled - Jenkins is accessible without authentication"